"""pyluxel.net.transport_steam -- Transport Steam P2P.

Usa SteamAPI (ctypes interno) per init/lobby/callbacks
+ SteamP2P (ctypes) per P2P messaging.

Richiede steam_api64.dll + steam_appid.txt nella directory del gioco.
App ID 480 (Spacewar) di default per dev gratuito.
"""

import struct
import time

from pyluxel.net.protocol import PROTOCOL_VERSION
from pyluxel.net.transport import Transport, TransportEvent
from pyluxel.net.steam_api import (
    SteamAPI, LOBBY_TYPE_PRIVATE, LOBBY_TYPE_FRIENDS_ONLY,
    LOBBY_TYPE_PUBLIC, LOBBY_TYPE_INVISIBLE,
    _CB_LOBBY_CHAT_UPDATE, _CB_P2P_SESSION_REQUEST,
)
from pyluxel.debug import cprint

# ── P2P Channels ──
CHANNEL_DATA = 0
CHANNEL_INTERNAL = 1

# ── Internal message types ──
_MSG_PING = 0x10
_MSG_PONG = 0x11
_PING_INTERVAL = 2.0  # seconds between pings


class SteamTransport(Transport):
    """Transport via Steam: SteamAPI (init/lobby/callbacks) + SteamP2P (packets)."""

    def __init__(self, app_id: int = 480):
        self._app_id = app_id
        self._steam: SteamAPI | None = None
        self._p2p = None  # SteamP2P instance
        self._is_host: bool = False
        self._connected: bool = False

        # Peer mapping
        self._peers: dict[int, int] = {}           # peer_id -> steam_id
        self._steam_to_peer: dict[int, int] = {}   # steam_id -> peer_id
        self._next_peer_id: int = 1
        self._local_steam_id: int = 0
        self._local_id: int = 0

        # Events queue
        self._events: list[TransportEvent] = []

        # Name cache: steam_id -> name
        self._name_cache: dict[int, str] = {}

        # Ping tracking
        self._ping_sent: dict[int, float] = {}   # peer_id -> timestamp
        self._peer_rtt: dict[int, float] = {}     # peer_id -> rtt in seconds
        self._last_ping_time: float = 0.0

        # Lobby
        self._lobby_id: int = 0

    def _init_steam(self):
        """Inizializza Steam API + P2P (lazy)."""
        if self._steam is not None:
            return

        # 1. SteamAPI per init/lobby/callbacks
        self._steam = SteamAPI()
        if not self._steam.init(self._app_id):
            raise RuntimeError(
                "Steam non inizializzato. Assicurati che:\n"
                "  1. Steam sia aperto e loggato\n"
                "  2. steam_api64.dll sia nella directory del gioco\n"
                "  3. steam_appid.txt con '480' sia nella directory del gioco"
            )

        self._local_steam_id = self._steam.get_steam_id()

        # Registra callbacks
        self._steam.on_lobby_changed(self._on_lobby_changed)

        cprint.info(f"Steam: inizializzato (App ID {self._app_id}, "
                    f"Steam ID {self._local_steam_id})")

        # 2. ctypes P2P per messaging (condividi la DLL)
        from pyluxel.net.steam_p2p import SteamP2P
        self._p2p = SteamP2P(dll=self._steam.dll)
        if not self._p2p.init():
            cprint.error("Steam: P2P ctypes init fallito!")
            self._p2p = None

    # ------------------------------------------------------------------
    # Transport interface
    # ------------------------------------------------------------------

    def listen(self, port: int) -> None:
        self._init_steam()
        self._is_host = True
        self._local_id = 0
        self._connected = True
        cprint.info("Steam: hosting attivo (P2P relay)")

    def connect(self, address: str, port: int) -> None:
        """Per Steam, 'address' e' lo Steam ID dell'host."""
        self._init_steam()
        self._is_host = False

        try:
            host_steam_id = int(address)
        except ValueError:
            cprint.error("Steam: indirizzo non valido. Usa lo Steam ID.")
            return

        self._peers[0] = host_steam_id
        self._steam_to_peer[host_steam_id] = 0
        if self._p2p:
            self._p2p.accept_session(host_steam_id)
        self._send_internal(host_steam_id,
                            struct.pack("<BH", 0x01, PROTOCOL_VERSION))
        self._connected = True
        cprint.info(f"Steam: connessione a {host_steam_id}")

    def poll(self) -> list[TransportEvent]:
        if self._steam is None:
            return []

        self._steam.run_callbacks()

        # Leggi P2P packets via ctypes
        if self._p2p and self._p2p.is_ready:
            for ch in (CHANNEL_DATA, CHANNEL_INTERNAL):
                msgs = self._p2p.receive(ch)
                for sender_id, data in msgs:
                    if ch == CHANNEL_DATA:
                        self._handle_data_message(sender_id, data)
                    else:
                        self._handle_internal_message(sender_id, data)

        # Periodic ping
        now = time.perf_counter()
        if self._connected and now - self._last_ping_time > _PING_INTERVAL:
            self._last_ping_time = now
            self._send_pings(now)

        events = list(self._events)
        self._events.clear()
        return events

    def send(self, peer_id: int, data: bytes, reliable: bool = True) -> None:
        steam_id = self._peers.get(peer_id)
        if steam_id is None or self._p2p is None:
            return
        self._p2p.send(steam_id, data, reliable, CHANNEL_DATA)

    def send_all(self, data: bytes, reliable: bool = True,
                 exclude: int | None = None) -> None:
        for pid in list(self._peers.keys()):
            if pid != exclude:
                self.send(pid, data, reliable)

    def disconnect_peer(self, peer_id: int) -> None:
        steam_id = self._peers.pop(peer_id, None)
        if steam_id:
            self._send_internal(steam_id, b"\x04")
            self._steam_to_peer.pop(steam_id, None)
            if self._p2p:
                self._p2p.close_session(steam_id)

    def close(self) -> None:
        if self._steam:
            if self._lobby_id:
                self.leave_lobby()
            for steam_id in list(self._peers.values()):
                self._send_internal(steam_id, b"\x04")
                if self._p2p:
                    self._p2p.close_session(steam_id)
            self._peers.clear()
            self._steam_to_peer.clear()
            self._steam.shutdown()
            self._steam = None
        self._connected = False

    def get_local_address(self) -> tuple[str, int]:
        return (str(self._local_steam_id), 0)

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def local_id(self) -> int:
        return self._local_id

    @property
    def peer_ids(self) -> list[int]:
        return list(self._peers.keys())

    # ------------------------------------------------------------------
    # Internal messaging
    # ------------------------------------------------------------------

    def _send_internal(self, steam_id: int, data: bytes):
        """Invia un messaggio sul canale interno."""
        if self._p2p and self._p2p.is_ready:
            self._p2p.send(steam_id, data, reliable=True, channel=CHANNEL_INTERNAL)

    def _handle_internal_message(self, sender_id: int, data: bytes):
        if not data:
            return
        msg_type = data[0]

        if msg_type == 0x01 and self._is_host:
            if sender_id not in self._steam_to_peer:
                # Verifica versione protocollo
                remote_ver = 0
                if len(data) >= 3:
                    remote_ver = struct.unpack_from("<H", data, 1)[0]
                if remote_ver != PROTOCOL_VERSION:
                    cprint.warning(f"Steam: rejected peer {sender_id} "
                                   f"(version {remote_ver} != {PROTOCOL_VERSION})")
                    return
                pid = self._next_peer_id
                self._next_peer_id += 1
                self._peers[pid] = sender_id
                self._steam_to_peer[sender_id] = pid
                accept = struct.pack("<BIH", 0x02, pid, PROTOCOL_VERSION)
                self._send_internal(sender_id, accept)
                self._events.append(TransportEvent("connect", pid,
                                                   address=str(sender_id), port=0))

        elif msg_type == 0x02 and not self._is_host:
            if len(data) >= 5:
                my_id = struct.unpack_from("<I", data, 1)[0]
                # Verifica versione protocollo
                remote_ver = 0
                if len(data) >= 7:
                    remote_ver = struct.unpack_from("<H", data, 5)[0]
                if remote_ver != PROTOCOL_VERSION:
                    cprint.warning(f"Steam: version mismatch with host "
                                   f"({remote_ver} != {PROTOCOL_VERSION})")
                    return
                self._local_id = my_id
                host_sid = self._peers.get(0, 0)
                self._events.append(TransportEvent("connect", 0,
                                                   address=str(host_sid), port=0))

        elif msg_type == 0x04:
            pid = self._steam_to_peer.pop(sender_id, None)
            if pid is not None:
                self._peers.pop(pid, None)
                self._ping_sent.pop(pid, None)
                self._peer_rtt.pop(pid, None)
                self._events.append(TransportEvent("disconnect", pid))

        elif msg_type == _MSG_PING:
            # Reply with pong (echo payload back)
            pong = bytes([_MSG_PONG]) + data[1:]
            self._send_internal(sender_id, pong)

        elif msg_type == _MSG_PONG:
            pid = self._steam_to_peer.get(sender_id)
            if pid is not None and len(data) >= 9:
                sent_time = struct.unpack_from("<d", data, 1)[0]
                sample = time.perf_counter() - sent_time
                prev = self._peer_rtt.get(pid, 0.0)
                # EMA smoothing (30% new sample, 70% previous)
                self._peer_rtt[pid] = sample if prev == 0.0 else prev * 0.7 + sample * 0.3
                self._ping_sent.pop(pid, None)

    def _handle_data_message(self, sender_id: int, data: bytes):
        pid = self._steam_to_peer.get(sender_id)
        if pid is None:
            return
        self._events.append(TransportEvent("data", pid, data))

    # ------------------------------------------------------------------
    # Ping
    # ------------------------------------------------------------------

    def _send_pings(self, now: float):
        """Invia ping a tutti i peer connessi."""
        payload = struct.pack("<Bd", _MSG_PING, now)
        for pid, steam_id in list(self._peers.items()):
            self._ping_sent[pid] = now
            self._send_internal(steam_id, payload)

    def get_peer_rtt(self, peer_id: int) -> float:
        return self._peer_rtt.get(peer_id, 0.0)

    # ------------------------------------------------------------------
    # Steam callbacks
    # ------------------------------------------------------------------

    def _on_lobby_changed(self, lobby_id, user_changed,
                          making_change, member_state_change):
        """Callback per LobbyChatUpdate_t (ID 506)."""
        cprint.info(f"Steam: lobby_changed user={user_changed}, "
                    f"state={member_state_change}")

        if member_state_change in (2, 4, 8):
            # Qualcuno ha lasciato
            pid = self._steam_to_peer.get(user_changed)
            if pid is not None:
                self._peers.pop(pid, None)
                self._steam_to_peer.pop(user_changed, None)
                self._events.append(TransportEvent("disconnect", pid))
                if self._p2p:
                    self._p2p.close_session(user_changed)
                cprint.info(f"Steam: peer {user_changed} ha lasciato")

        elif member_state_change in (0, 1):
            # Qualcuno e' entrato
            if user_changed != self._local_steam_id:
                # Accetta P2P session proattivamente
                if self._p2p:
                    self._p2p.accept_session(user_changed)

                if self._is_host and user_changed not in self._steam_to_peer:
                    members = self.get_lobby_members_ids()
                    pid = (members.index(user_changed)
                           if user_changed in members
                           else self._next_peer_id)
                    if pid == 0:
                        pid = self._next_peer_id
                    self._next_peer_id = max(self._next_peer_id, pid + 1)

                    self._peers[pid] = user_changed
                    self._steam_to_peer[user_changed] = pid
                    self._events.append(TransportEvent("connect", pid,
                                                       address=str(user_changed),
                                                       port=0))
                    cprint.info(f"Steam: {user_changed} entrato, peer_id={pid}")

    # ------------------------------------------------------------------
    # Lobby API
    # ------------------------------------------------------------------

    def create_lobby(self, lobby_type: int = LOBBY_TYPE_FRIENDS_ONLY,
                     max_members: int = 4, callback=None) -> None:
        self._init_steam()

        def _on_created(lobby_id):
            if lobby_id:
                self._lobby_id = lobby_id
                cprint.ok(f"Steam: lobby creata! ID: {lobby_id}")
            else:
                cprint.error("Steam: errore creazione lobby")
            if callback:
                callback(lobby_id)

        self._steam.create_lobby(lobby_type, max_members, _on_created)
        cprint.info(f"Steam: creazione lobby (type={lobby_type}, "
                    f"max={max_members})...")

    def join_lobby(self, lobby_id: int, callback=None) -> None:
        self._init_steam()

        def _on_joined(lid):
            if not lid:
                cprint.error("Steam: errore join lobby")
                if callback:
                    callback(0)
                return

            self._lobby_id = lid
            members = self.get_lobby_members_ids()
            cprint.info(f"Steam: lobby members: {members}")

            # Il mio local_id = indice nella lobby
            for i, mid in enumerate(members):
                if mid == self._local_steam_id:
                    self._local_id = i
                    break

            # Registra host e accetta P2P
            for member_id in members:
                if member_id != self._local_steam_id:
                    if member_id not in self._steam_to_peer:
                        self._peers[0] = member_id
                        self._steam_to_peer[member_id] = 0
                        self._connected = True
                        if self._p2p:
                            self._p2p.accept_session(member_id)
                        self._events.append(TransportEvent("connect", 0,
                                                           address=str(member_id),
                                                           port=0))
                        cprint.info(f"Steam: joined lobby, host={member_id}, "
                                    f"my_id={self._local_id}")
                    break

            if callback:
                callback(lid)

        self._steam.join_lobby(lobby_id, _on_joined)
        cprint.info(f"Steam: joining lobby {lobby_id}...")

    def leave_lobby(self) -> None:
        if self._lobby_id and self._steam:
            self._steam.leave_lobby(self._lobby_id)
            self._lobby_id = 0

    def set_lobby_data(self, key: str, value: str) -> bool:
        if not self._lobby_id or not self._steam:
            return False
        return self._steam.set_lobby_data(self._lobby_id, key, value)

    def get_lobby_data(self, key: str) -> str:
        if not self._lobby_id or not self._steam:
            return ""
        return self._steam.get_lobby_data(self._lobby_id, key)

    def get_lobby_members_ids(self) -> list[int]:
        if not self._lobby_id or not self._steam:
            return []
        return self._steam.get_lobby_members(self._lobby_id)

    # ------------------------------------------------------------------
    # Friends & Rich Presence
    # ------------------------------------------------------------------

    def invite_friend(self, steam_id: int) -> bool:
        """Invita un amico alla lobby corrente."""
        if not self._lobby_id or not self._steam:
            return False
        return self._steam.invite_user_to_lobby(self._lobby_id, steam_id)

    def show_invite_overlay(self) -> None:
        """Apre l'overlay Steam per invitare amici alla lobby."""
        if not self._lobby_id or not self._steam:
            return
        self._steam.activate_invite_overlay(self._lobby_id)

    def get_friend_list(self) -> list[dict]:
        """Ritorna la lista amici Steam.

        Returns:
            ``[{"steam_id": int, "name": str, "state": int, "online": bool}, ...]``
        """
        if not self._steam:
            return []
        count = self._steam.get_friend_count()
        friends = []
        for i in range(count):
            sid = self._steam.get_friend_by_index(i)
            if not sid:
                continue
            state = self._steam.get_friend_persona_state(sid)
            friends.append({
                "steam_id": sid,
                "name": self._steam.get_friend_persona_name(sid),
                "state": state,
                "online": state != 0,
            })
        return friends

    def get_lobby_members(self) -> list[dict]:
        """Ritorna i membri della lobby con nome e ruolo.

        Returns:
            ``[{"steam_id": int, "name": str, "is_host": bool}, ...]``
        """
        if not self._lobby_id or not self._steam:
            return []
        ids = self.get_lobby_members_ids()
        host_id = ids[0] if ids else 0
        members = []
        for sid in ids:
            name = self._resolve_name(sid)
            members.append({
                "steam_id": sid,
                "name": name,
                "is_host": sid == host_id,
            })
        return members

    def set_rich_presence(self, key: str, value: str) -> bool:
        """Imposta una chiave Rich Presence su Steam."""
        if not self._steam:
            return False
        return self._steam.set_rich_presence(key, value)

    def clear_rich_presence(self) -> None:
        """Rimuovi tutte le chiavi Rich Presence."""
        if not self._steam:
            return
        self._steam.clear_rich_presence()

    @property
    def lobby_id(self) -> int:
        return self._lobby_id

    def get_player_name(self, steam_id: int) -> str:
        """Ritorna il nome Steam di un giocatore dato il suo Steam ID."""
        return self._resolve_name(steam_id)

    def _resolve_name(self, steam_id: int) -> str:
        """Risolvi il nome di uno steam_id, con cache."""
        cached = self._name_cache.get(steam_id)
        if cached:
            return cached
        if not self._steam:
            return ""
        if steam_id == self._local_steam_id:
            name = self._steam.get_persona_name()
            if name:
                self._name_cache[steam_id] = name
                return name
        # Per i remoti il nome arriva via NetPlayer.name (synced),
        # non usiamo get_friend_persona_name (crash con alcuni build della DLL)
        return ""

    def get_local_name(self) -> str:
        """Ritorna il nome Steam del giocatore locale."""
        return self._resolve_name(self._local_steam_id) if self._local_steam_id else ""

    @property
    def steam_id(self) -> int:
        return self._local_steam_id
