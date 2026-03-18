"""pyluxel.net.protocol -- Protocollo binario per il networking.

Header compatto (11 bytes) + payload variabile.
Serializzazione/deserializzazione tramite struct.pack per efficienza.
"""

import struct
from dataclasses import dataclass

# ── Header format ──
# [0]     u8   msg_type
# [1-2]   u16  sequence
# [3-4]   u16  ack_seq
# [5-8]   u32  ack_bits
# [9-10]  u16  payload_len
# [11..]  payload

HEADER_FORMAT = "<BHHIH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 11 bytes

# Protocol version — bumped when wire format changes
PROTOCOL_VERSION = 5


class MsgType:
    """Tipi di messaggio del protocollo."""
    # Connection
    CONNECT_REQ     = 0x01
    CONNECT_ACK     = 0x02
    CONNECT_REJECT  = 0x03
    DISCONNECT      = 0x04
    PING            = 0x05
    PONG            = 0x06
    TIME_SYNC       = 0x07

    # Data
    STATE_SYNC      = 0x10
    RPC_CALL        = 0x11
    RAW_DATA        = 0x12

    # Peer discovery
    PEER_LIST       = 0x08  # [count:u16] per nodo: [name_len:u8] [owner:u32] [obj_id:u32] [name:bytes]

    # Node spawn/despawn
    SPAWN_NODE      = 0x09
    DESPAWN_NODE    = 0x0A

    # Events
    NET_EVENT       = 0x13

    # Lobby
    LOBBY_INFO      = 0x20
    LOBBY_PLAYERS   = 0x21


# ── Compression ──
COMPRESSION_FLAG      = 0x80   # bit 7 di msg_type indica payload compresso
COMPRESSION_THRESHOLD = 128    # comprimere solo payload > 128 bytes


# ── Type tags per serializzazione ──

class TypeTag:
    BOOL    = 0
    INT     = 1
    FLOAT   = 2
    STR     = 3
    VEC2    = 4
    BYTES   = 5


@dataclass(slots=True)
class Packet:
    """Pacchetto decodificato."""
    msg_type: int
    sequence: int
    ack_seq: int
    ack_bits: int
    payload: bytes


def pack_header(msg_type: int, sequence: int, ack_seq: int,
                ack_bits: int, payload: bytes) -> bytes:
    """Crea un pacchetto completo: header + payload."""
    header = struct.pack(HEADER_FORMAT, msg_type, sequence,
                         ack_seq, ack_bits, len(payload))
    return header + payload


# Payload massimo accettato (protegge da pacchetti malevoli)
MAX_PAYLOAD_SIZE = 8192


def unpack_header(data: bytes) -> Packet | None:
    """Decodifica un pacchetto. Ritorna None se dati insufficienti o troppo grandi."""
    if len(data) < HEADER_SIZE:
        return None
    msg_type, seq, ack_seq, ack_bits, payload_len = struct.unpack(
        HEADER_FORMAT, data[:HEADER_SIZE])
    if payload_len > MAX_PAYLOAD_SIZE:
        return None  # Payload troppo grande, scarta
    if len(data) < HEADER_SIZE + payload_len:
        return None
    payload = data[HEADER_SIZE:HEADER_SIZE + payload_len]
    return Packet(msg_type, seq, ack_seq, ack_bits, payload)


# ── Serializzazione valori ──

def pack_value(value) -> bytes:
    """Serializza un valore con type tag prefisso."""
    if isinstance(value, bool):
        return struct.pack("<B?", TypeTag.BOOL, value)
    elif isinstance(value, int):
        return struct.pack("<Bi", TypeTag.INT, value)
    elif isinstance(value, float):
        return struct.pack("<Bf", TypeTag.FLOAT, value)
    elif isinstance(value, str):
        encoded = value.encode("utf-8")
        return struct.pack("<BH", TypeTag.STR, len(encoded)) + encoded
    elif isinstance(value, (tuple, list)) and len(value) == 2:
        return struct.pack("<Bff", TypeTag.VEC2, value[0], value[1])
    elif isinstance(value, (bytes, bytearray)):
        return struct.pack("<BH", TypeTag.BYTES, len(value)) + value
    else:
        raise TypeError(f"Tipo non serializzabile: {type(value)}")


def unpack_value(data: bytes, offset: int = 0) -> tuple:
    """Deserializza un valore. Ritorna (valore, nuovo_offset)."""
    tag = data[offset]
    offset += 1

    if tag == TypeTag.BOOL:
        val = struct.unpack_from("<?", data, offset)[0]
        return val, offset + 1
    elif tag == TypeTag.INT:
        val = struct.unpack_from("<i", data, offset)[0]
        return val, offset + 4
    elif tag == TypeTag.FLOAT:
        val = struct.unpack_from("<f", data, offset)[0]
        return val, offset + 4
    elif tag == TypeTag.STR:
        length = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        val = data[offset:offset + length].decode("utf-8")
        return val, offset + length
    elif tag == TypeTag.VEC2:
        x, y = struct.unpack_from("<ff", data, offset)
        return (x, y), offset + 8
    elif tag == TypeTag.BYTES:
        length = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        val = bytes(data[offset:offset + length])
        return val, offset + length
    else:
        raise ValueError(f"Type tag sconosciuto: {tag}")


def pack_values(*values) -> bytes:
    """Serializza una sequenza di valori."""
    buf = bytearray()
    for v in values:
        buf.extend(pack_value(v))
    return bytes(buf)


def unpack_values(data: bytes, count: int, offset: int = 0) -> tuple:
    """Deserializza N valori. Ritorna (lista_valori, nuovo_offset)."""
    values = []
    for _ in range(count):
        val, offset = unpack_value(data, offset)
        values.append(val)
    return values, offset
