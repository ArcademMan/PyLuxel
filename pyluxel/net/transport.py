"""pyluxel.net.transport -- Transport ABC e UDPTransport.

Il Transport e' il layer di rete pluggabile: gestisce socket/connessioni
e produce TransportEvent consumati dal NetworkManager.
"""

import socket
import struct
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from pyluxel import cprint
from pyluxel.net.channel import ReliableChannel
from pyluxel.net.protocol import (
    MsgType, HEADER_SIZE, pack_header, unpack_header, PROTOCOL_VERSION,
)


@dataclass(slots=True)
class TransportEvent:
    """Evento prodotto dal transport layer."""
    type: str               # "connect" | "disconnect" | "data"
    peer_id: int = 0
    data: bytes | None = None
    address: str = ""
    port: int = 0


class Transport(ABC):
    """Interfaccia astratta per il transport layer."""

    @abstractmethod
    def listen(self, port: int) -> None:
        """Avvia in modalita' host sulla porta data."""

    @abstractmethod
    def connect(self, address: str, port: int) -> None:
        """Connettiti a un host remoto."""

    @abstractmethod
    def poll(self) -> list[TransportEvent]:
        """Legge eventi in arrivo (non-blocking)."""

    @abstractmethod
    def send(self, peer_id: int, data: bytes, reliable: bool = True) -> None:
        """Invia dati a un peer specifico."""

    @abstractmethod
    def send_all(self, data: bytes, reliable: bool = True,
                 exclude: int | None = None) -> None:
        """Invia dati a tutti i peer connessi."""

    @abstractmethod
    def disconnect_peer(self, peer_id: int) -> None:
        """Disconnetti un peer specifico."""

    @abstractmethod
    def close(self) -> None:
        """Chiudi il transport e rilascia risorse."""

    @abstractmethod
    def get_local_address(self) -> tuple[str, int]:
        """Ritorna (ip, port) locali."""


# ── Stato interno per un peer UDP ──

@dataclass
class _UDPPeer:
    peer_id: int
    address: tuple[str, int]
    channel: ReliableChannel = field(default_factory=ReliableChannel)
    last_seen: float = field(default_factory=time.perf_counter)
    ping_sent: float = 0.0
    rtt: float = 0.0


class UDPTransport(Transport):
    """Transport basato su UDP con reliability opzionale.

    Gestisce handshake, keep-alive e canali reliable/unreliable.
    """

    TIMEOUT = 10.0          # secondi senza pacchetti → disconnessione
    PING_INTERVAL = 2.0     # secondi tra ping
    MAX_PACKET_SIZE = 1400  # MTU safe

    def __init__(self):
        self._sock: socket.socket | None = None
        self._is_host: bool = False
        self._peers: dict[int, _UDPPeer] = {}
        self._addr_to_id: dict[tuple[str, int], int] = {}
        self._next_peer_id: int = 1
        self._local_port: int = 0
        self._host_addr: tuple[str, int] | None = None
        self._connected: bool = False
        self._last_ping_time: float = 0.0

    def listen(self, port: int) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)
        self._sock.bind(("0.0.0.0", port))
        self._local_port = port
        self._is_host = True
        self._connected = True

    def connect(self, address: str, port: int) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)
        self._sock.bind(("0.0.0.0", 0))
        self._local_port = self._sock.getsockname()[1]
        self._host_addr = (address, port)
        self._is_host = False

        # Invia richiesta di connessione con versione protocollo
        ver_payload = struct.pack("<H", PROTOCOL_VERSION)
        packet = pack_header(MsgType.CONNECT_REQ, 0, 0, 0, ver_payload)
        self._sock.sendto(packet, self._host_addr)

    def poll(self) -> list[TransportEvent]:
        if self._sock is None:
            return []

        events: list[TransportEvent] = []
        now = time.perf_counter()

        # Leggi tutti i pacchetti disponibili
        while True:
            try:
                data, addr = self._sock.recvfrom(self.MAX_PACKET_SIZE)
            except BlockingIOError:
                break  # Nessun dato disponibile (normale)
            except OSError as e:
                cprint.warning(e)
                break

            packet = unpack_header(data)
            if packet is None:
                continue

            # Gestisci in base al tipo
            evt = self._handle_packet(packet, addr, now)
            if evt is not None:
                events.append(evt)

        # Resend pacchetti reliable
        for peer in self._peers.values():
            resends = peer.channel.get_resends()
            for pkt in resends:
                try:
                    self._sock.sendto(pkt, peer.address)
                except OSError as e:
                    cprint.warning(e)

        # Ping periodico
        if now - self._last_ping_time > self.PING_INTERVAL:
            self._last_ping_time = now
            self._send_pings(now)

        # Timeout check
        disconnected = []
        for pid, peer in self._peers.items():
            if now - peer.last_seen > self.TIMEOUT:
                disconnected.append(pid)

        for pid in disconnected:
            peer = self._peers.pop(pid)
            self._addr_to_id.pop(peer.address, None)
            events.append(TransportEvent("disconnect", pid))

        return events

    def _handle_packet(self, packet, addr: tuple[str, int],
                       now: float) -> TransportEvent | None:
        """Gestisce un pacchetto ricevuto."""

        # ── Host: nuova connessione ──
        if packet.msg_type == MsgType.CONNECT_REQ and self._is_host:
            if addr not in self._addr_to_id:
                # Verifica versione protocollo
                remote_ver = 0
                if len(packet.payload) >= 2:
                    remote_ver = struct.unpack_from("<H", packet.payload)[0]
                if remote_ver != PROTOCOL_VERSION:
                    reject = pack_header(MsgType.CONNECT_REJECT, 0, 0, 0, b"")
                    self._sock.sendto(reject, addr)
                    return None

                pid = self._next_peer_id
                self._next_peer_id += 1
                peer = _UDPPeer(pid, addr)
                peer.last_seen = now
                self._peers[pid] = peer
                self._addr_to_id[addr] = pid

                # Manda accept con l'ID assegnato + versione
                payload = struct.pack("<IH", pid, PROTOCOL_VERSION)
                ack = pack_header(MsgType.CONNECT_ACK, 0, 0, 0, payload)
                self._sock.sendto(ack, addr)

                return TransportEvent("connect", pid, address=addr[0], port=addr[1])
            return None

        # ── Client: accept ricevuto ──
        if packet.msg_type == MsgType.CONNECT_ACK and not self._is_host:
            if not self._connected and self._host_addr:
                if len(packet.payload) >= 6:
                    my_id, remote_ver = struct.unpack_from("<IH", packet.payload)
                elif len(packet.payload) >= 4:
                    my_id = struct.unpack_from("<I", packet.payload)[0]
                    remote_ver = 0  # vecchio server senza versione
                else:
                    return None
                if remote_ver != PROTOCOL_VERSION:
                    return None  # versione incompatibile
                pid = 0  # host e' sempre peer 0 per il client
                peer = _UDPPeer(pid, self._host_addr)
                peer.last_seen = now
                self._peers[pid] = peer
                self._addr_to_id[self._host_addr] = pid
                self._connected = True
                self._local_id = my_id
                return TransportEvent("connect", pid,
                                      address=self._host_addr[0],
                                      port=self._host_addr[1])
            return None

        # ── Peer noto ──
        pid = self._addr_to_id.get(addr)
        if pid is None:
            return None

        peer = self._peers.get(pid)
        if peer is None:
            return None

        peer.last_seen = now

        if packet.msg_type == MsgType.DISCONNECT:
            self._peers.pop(pid, None)
            self._addr_to_id.pop(addr, None)
            return TransportEvent("disconnect", pid)

        if packet.msg_type == MsgType.PING:
            # Rispondi con pong
            pong = pack_header(MsgType.PONG, 0, 0, 0, packet.payload)
            self._sock.sendto(pong, addr)
            return None

        if packet.msg_type == MsgType.PONG:
            if peer.ping_sent > 0:
                peer.rtt = now - peer.ping_sent
                peer.ping_sent = 0.0
            return None

        # ── Dati ──
        if packet.msg_type in (MsgType.STATE_SYNC, MsgType.RPC_CALL,
                                MsgType.RAW_DATA, MsgType.TIME_SYNC,
                                MsgType.NET_EVENT):
            is_reliable = bool(packet.ack_bits & self._RELIABLE_FLAG)

            if is_reliable:
                processed = peer.channel.process_incoming(packet.payload)
                if processed is not None:
                    full = struct.pack("<B", packet.msg_type) + processed
                    return TransportEvent("data", pid, full)
                # Duplicato reliable: scarta
                return None
            else:
                # Unreliable: passa il payload diretto
                if len(packet.payload) > 0:
                    full = struct.pack("<B", packet.msg_type) + packet.payload
                    return TransportEvent("data", pid, full)

        return None

    def _send_pings(self, now: float):
        """Invia ping a tutti i peer."""
        payload = struct.pack("<d", now)
        ping = pack_header(MsgType.PING, 0, 0, 0, payload)
        for peer in self._peers.values():
            peer.ping_sent = now
            try:
                self._sock.sendto(ping, peer.address)
            except OSError as e:
                cprint.warning(e)

    # Flag reliable: usato nel campo ack_bits dell'header
    # (non piu' in sequence, cosi' il channel ha tutti i 16 bit)
    _RELIABLE_FLAG = 0x80000000

    def send(self, peer_id: int, data: bytes, reliable: bool = True) -> None:
        peer = self._peers.get(peer_id)
        if peer is None or self._sock is None:
            return

        if reliable:
            seq, wrapped = peer.channel.wrap_reliable(data)
            packet = pack_header(MsgType.RAW_DATA, seq, 0, self._RELIABLE_FLAG, wrapped)
        else:
            packet = pack_header(MsgType.RAW_DATA, 0, 0, 0, data)

        try:
            self._sock.sendto(packet, peer.address)
        except OSError as e:
            cprint.warning(e)

    def send_all(self, data: bytes, reliable: bool = True,
                 exclude: int | None = None) -> None:
        for pid in self._peers:
            if pid != exclude:
                self.send(pid, data, reliable)

    def disconnect_peer(self, peer_id: int) -> None:
        peer = self._peers.pop(peer_id, None)
        if peer and self._sock:
            packet = pack_header(MsgType.DISCONNECT, 0, 0, 0, b"")
            try:
                self._sock.sendto(packet, peer.address)
            except OSError as e:
                cprint.warning(e)
            self._addr_to_id.pop(peer.address, None)

    def close(self) -> None:
        if self._sock:
            # Notifica tutti della disconnessione
            packet = pack_header(MsgType.DISCONNECT, 0, 0, 0, b"")
            for peer in self._peers.values():
                try:
                    self._sock.sendto(packet, peer.address)
                except OSError:
                    pass
            self._peers.clear()
            self._addr_to_id.clear()
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self._connected = False

    def get_local_address(self) -> tuple[str, int]:
        return ("0.0.0.0", self._local_port)

    def get_peer_rtt(self, peer_id: int) -> float:
        peer = self._peers.get(peer_id)
        return peer.rtt if peer else 0.0

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def local_id(self) -> int:
        if self._is_host:
            return 0
        return getattr(self, "_local_id", 0)

    @property
    def peer_ids(self) -> list[int]:
        return list(self._peers.keys())
