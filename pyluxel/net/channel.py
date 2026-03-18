"""pyluxel.net.channel -- Reliable delivery layer per UDP.

Sliding window con sequence numbers, ack bitmask e resend queue.
Non usato con Steam (reliability nativa).
"""

import struct
import time

# Reliable header: prepended al payload prima dell'header di protocollo
# [0-1]  u16  sequence
# [2-3]  u16  ack_seq (ultimo seq ricevuto)
# [4-7]  u32  ack_bits (bitmask dei 32 seq precedenti)
RELIABLE_HEADER = "<HHI"
RELIABLE_HEADER_SIZE = struct.calcsize(RELIABLE_HEADER)  # 8 bytes

WINDOW_SIZE = 1024
RESEND_INTERVAL = 0.15    # secondi prima di re-inviare
MAX_RESEND_ATTEMPTS = 10


class ReliableChannel:
    """Canale affidabile con ordinamento su UDP."""

    def __init__(self):
        self._local_seq: int = 0
        self._remote_seq: int = 0
        self._ack_bits: int = 0

        # Pacchetti in attesa di ack: seq -> (send_time, data, attempts)
        self._pending: dict[int, tuple[float, bytes, int]] = {}

        # Sequenze gia' ricevute (per dedup)
        self._received: set[int] = set()

    def next_seq(self) -> int:
        """Ritorna il prossimo sequence number e avanza."""
        seq = self._local_seq
        self._local_seq = (self._local_seq + 1) % 65536
        return seq

    def wrap_reliable(self, data: bytes) -> tuple[int, bytes]:
        """Wrappa dati con header di reliability.

        Returns:
            (sequence, wrapped_data)
        """
        seq = self.next_seq()
        header = struct.pack(RELIABLE_HEADER, seq,
                             self._remote_seq, self._ack_bits)
        wrapped = header + data
        self._pending[seq] = (time.perf_counter(), wrapped, 0)
        return seq, wrapped

    def process_incoming(self, data: bytes) -> bytes | None:
        """Processa dati in arrivo con header reliable.

        Aggiorna ack state e ritorna il payload, oppure None se duplicato.
        """
        if len(data) < RELIABLE_HEADER_SIZE:
            return None

        seq, ack_seq, ack_bits = struct.unpack_from(RELIABLE_HEADER, data)
        payload = data[RELIABLE_HEADER_SIZE:]

        # Processa gli ack ricevuti dal peer
        self._process_acks(ack_seq, ack_bits)

        # Dedup: gia' ricevuto?
        if seq in self._received:
            return None
        self._received.add(seq)

        # Limita la dimensione del set received (wraparound-safe)
        if len(self._received) > WINDOW_SIZE:
            self._received = {
                s for s in self._received
                if (seq - s) % 65536 < WINDOW_SIZE
            }

        # Aggiorna remote_seq e ack_bits
        # Wraparound-safe: differenza signed in spazio u16
        diff = (seq - self._remote_seq) % 65536
        is_newer = 0 < diff < 32768

        if is_newer:
            # Shifta ack_bits: il vecchio remote_seq diventa bit 0
            if diff <= 32:
                self._ack_bits = ((self._ack_bits << diff) | (1 << (diff - 1))) & 0xFFFFFFFF
            else:
                self._ack_bits = 0
            self._remote_seq = seq
        else:
            # Pacchetto piu' vecchio: setta il bit corrispondente
            diff_old = (self._remote_seq - seq) % 65536
            if 0 < diff_old <= 32:
                self._ack_bits |= (1 << (diff_old - 1))

        return payload

    def _process_acks(self, ack_seq: int, ack_bits: int):
        """Rimuove dalla pending i pacchetti confermati."""
        # Il peer conferma ack_seq
        self._pending.pop(ack_seq, None)

        # E i 32 precedenti tramite bitmask
        for i in range(32):
            if ack_bits & (1 << i):
                confirmed = (ack_seq - 1 - i) % 65536
                self._pending.pop(confirmed, None)

    def get_resends(self) -> list[bytes]:
        """Ritorna i pacchetti da re-inviare."""
        now = time.perf_counter()
        resends = []
        expired = []

        to_update: list[tuple[int, float, bytes, int]] = []

        for seq, (send_time, data, attempts) in self._pending.items():
            if now - send_time > RESEND_INTERVAL:
                if attempts >= MAX_RESEND_ATTEMPTS:
                    expired.append(seq)
                else:
                    to_update.append((seq, now, data, attempts + 1))
                    resends.append(data)

        for seq in expired:
            del self._pending[seq]
        for seq, t, data, att in to_update:
            self._pending[seq] = (t, data, att)

        return resends

    @property
    def pending_count(self) -> int:
        """Numero di pacchetti in attesa di conferma."""
        return len(self._pending)

    def get_ack_header(self) -> bytes:
        """Ritorna solo l'header ack corrente (per piggyback su unreliable)."""
        return struct.pack(RELIABLE_HEADER, 0, self._remote_seq, self._ack_bits)
