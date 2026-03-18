"""pyluxel.net.sync -- State synchronization con descriptor ``synced()``.

Uso::

    class Player:
        x = synced(0.0, interpolate=True, lerp_speed=15.0)
        y = synced(0.0, interpolate=True, lerp_speed=15.0)
        health = synced(100, reliable=True)

        def __init__(self, owner: int):
            self._net_owner = owner

Solo il proprietario (_net_owner == Net.local_id) puo' scrivere.
Le modifiche vengono marcate dirty e inviate al prossimo sync tick.
I peer remoti ricevono i valori e (opzionalmente) li interpolano.
"""

import struct

from pyluxel import cprint
from pyluxel.net.protocol import pack_value, unpack_value

# Cache lazy per evitare import in hot path
_net_ref = None


def _get_net():
    global _net_ref
    if _net_ref is None:
        from pyluxel.net import Net
        _net_ref = Net
    return _net_ref


def _values_equal(a, b) -> bool:
    """Confronto con tolleranza per float/vec2, evita dirty da rumore FP."""
    if type(a) != type(b):
        return False
    if isinstance(a, float):
        return abs(a - b) < 0.001
    if isinstance(a, tuple) and len(a) == 2:
        return abs(a[0] - b[0]) < 0.001 and abs(a[1] - b[1]) < 0.001
    return a == b


class synced:
    """Descriptor per variabili sincronizzate in rete.

    Args:
        default: Valore iniziale.
        reliable: Se True, usa canale affidabile (per valori critici).
        interpolate: Se True, i valori ricevuti vengono interpolati.
        lerp_speed: Velocita' di interpolazione (unita'/secondo).
    """

    def __init__(self, default=None, *, reliable: bool = False,
                 interpolate: bool = False, lerp_speed: float = 10.0):
        self.default = default
        self.reliable = reliable
        self.interpolate = interpolate
        self.lerp_speed = lerp_speed
        self.attr_name: str = ""
        self.field_name: str = ""

    def __set_name__(self, owner, name):
        self.field_name = name
        self.attr_name = f"_sync_{name}"
        self._target_name = f"_sync_target_{name}"

        # Registra nel dict dei sync fields della classe
        # Usa __dict__ per non ereditare dal parent (hasattr risale la MRO)
        if "_sync_fields" not in owner.__dict__:
            # Copia i campi del parent se esistono, cosi' le subclass li vedono
            parent_fields = getattr(owner, "_sync_fields", {})
            owner._sync_fields = dict(parent_fields)
        owner._sync_fields[name] = self

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, self.attr_name, self.default)

    def __set__(self, obj, value):
        old = getattr(obj, self.attr_name, self.default)
        setattr(obj, self.attr_name, value)

        # Se siamo il proprietario e il valore e' cambiato, marca dirty
        if not _values_equal(old, value) and hasattr(obj, "_net_dirty"):
            try:
                net = _get_net()
                owner = getattr(obj, "_net_owner", -1)
                if owner == net.local_id:
                    obj._net_dirty.add(self.field_name)
            except ImportError as e:
                cprint.warning(e)


def _get_sync_fields(obj) -> dict[str, "synced"]:
    """Ritorna i campi synced di un oggetto."""
    return getattr(type(obj), "_sync_fields", {})


# Cache: class -> {field_name: index}
_field_index_cache: dict[type, dict[str, int]] = {}


def _get_field_index(cls, fields: dict[str, "synced"]) -> dict[str, int]:
    """Ritorna mapping nome->indice, con cache per classe."""
    idx = _field_index_cache.get(cls)
    if idx is None:
        idx = {name: i for i, name in enumerate(fields)}
        _field_index_cache[cls] = idx
    return idx


def clear_sync_caches():
    """Pulisce le cache module-level. Chiamato da disconnect()."""
    _field_index_cache.clear()


def _next_sync_seq(obj) -> int:
    """Incrementa e ritorna il sequence number per un oggetto (wraparound u16)."""
    seq = getattr(obj, "_net_sync_seq", 0)
    seq = (seq + 1) % 65536
    obj._net_sync_seq = seq
    return seq


def _seq_newer(new_seq: int, old_seq: int) -> bool:
    """True se new_seq e' piu' recente di old_seq (wraparound-safe, u16)."""
    diff = (new_seq - old_seq) % 65536
    return 0 < diff < 32768


def build_sync_packet(obj_id: int, obj: object,
                      dirty: set[str],
                      net_time: float = 0.0) -> bytes | None:
    """Costruisce il payload di un pacchetto STATE_SYNC per i campi dirty.

    Formato:
        [obj_id: u32] [seq: u16] [timestamp: f32] [field_count: u8]
        Per ogni campo: [field_index: u8] [packed_value]
    """
    fields = _get_sync_fields(obj)
    if not fields:
        return None

    index_map = _get_field_index(type(obj), fields)
    parts = []
    count = 0

    for name in dirty:
        if name not in fields:
            continue
        idx = index_map[name]
        descriptor = fields[name]
        value = getattr(obj, descriptor.attr_name, descriptor.default)
        try:
            packed = pack_value(value)
            parts.append(struct.pack("<B", idx) + packed)
            count += 1
        except TypeError as e:
            cprint.warning(e)
            continue

    if count == 0:
        return None

    seq = _next_sync_seq(obj)
    header = struct.pack("<IHfB", obj_id, seq, net_time, count)
    return header + b"".join(parts)


def build_full_sync_packet(obj_id: int, obj: object,
                           net_time: float = 0.0) -> bytes | None:
    """Costruisce un pacchetto con TUTTI i campi sync (per nuovi peer)."""
    fields = _get_sync_fields(obj)
    if not fields:
        return None

    parts = []
    count = 0

    for idx, (name, descriptor) in enumerate(fields.items()):
        value = getattr(obj, descriptor.attr_name, descriptor.default)
        try:
            packed = pack_value(value)
            parts.append(struct.pack("<B", idx) + packed)
            count += 1
        except TypeError as e:
            cprint.warning(e)
            continue

    if count == 0:
        return None

    seq = _next_sync_seq(obj)
    header = struct.pack("<IHfB", obj_id, seq, net_time, count)
    return header + b"".join(parts)


def apply_sync_packet(manager, peer_id: int, payload: bytes):
    """Applica un pacchetto STATE_SYNC ricevuto.

    Controlla il sequence number per scartare pacchetti arrivati fuori ordine
    (possibile con invio unreliable). Wraparound-safe su 16 bit.
    Salva il timestamp per interpolazione temporale.
    """
    if len(payload) < 11:
        return

    obj_id, seq, timestamp, field_count = struct.unpack_from("<IHfB", payload)
    offset = 11

    obj = manager._registered.get(obj_id)
    if obj is None:
        return

    # Sequence check: scarta pacchetti piu' vecchi dell'ultimo ricevuto
    if hasattr(obj, "_net_sync_recv_seq"):
        if not _seq_newer(seq, obj._net_sync_recv_seq):
            return  # Stale packet, drop
    obj._net_sync_recv_seq = seq

    # Salva timestamp per interpolazione temporale
    if timestamp > 0.0:
        obj._net_sync_prev_time = getattr(obj, "_net_sync_recv_time", timestamp)
        obj._net_sync_recv_time = timestamp

    fields = _get_sync_fields(obj)
    if not fields:
        return

    field_names = list(fields.keys())

    for _ in range(field_count):
        if offset >= len(payload):
            break

        field_idx = payload[offset]
        offset += 1

        if field_idx >= len(field_names):
            break

        name = field_names[field_idx]
        descriptor = fields[name]

        try:
            value, offset = unpack_value(payload, offset)
        except (ValueError, struct.error) as e:
            cprint.warning(e)
            break

        if descriptor.interpolate:
            # Salva come target per interpolazione
            setattr(obj, descriptor._target_name, value)
            # Inizializza il valore corrente se non esiste
            if not hasattr(obj, descriptor.attr_name):
                setattr(obj, descriptor.attr_name, value)
        else:
            # Applica direttamente (bypass descriptor per non triggerare dirty)
            setattr(obj, descriptor.attr_name, value)


def update_interpolation(obj: object, dt: float, net_time: float = 0.0):
    """Aggiorna interpolazione per un oggetto remoto.

    Se net_time > 0 e l'oggetto ha timestamp di sync, usa interpolazione
    temporale: calcola t dal tempo trascorso tra gli ultimi due snapshot.
    Altrimenti usa lerp esponenziale (fallback).
    """
    fields = _get_sync_fields(obj)
    if not fields:
        return

    # Calcola t basato su timestamp se disponibile
    time_based_t = -1.0
    if net_time > 0.0:
        recv_time = getattr(obj, "_net_sync_recv_time", 0.0)
        prev_time = getattr(obj, "_net_sync_prev_time", 0.0)
        if recv_time > 0.0 and prev_time > 0.0 and recv_time > prev_time:
            interval = recv_time - prev_time
            elapsed = net_time - prev_time
            time_based_t = min(1.0, elapsed / interval)

    for name, descriptor in fields.items():
        if not descriptor.interpolate:
            continue

        target = getattr(obj, descriptor._target_name, None)
        if target is None:
            continue

        current = getattr(obj, descriptor.attr_name, descriptor.default)

        # Scegli t: temporale se disponibile, altrimenti lerp esponenziale
        if time_based_t >= 0.0:
            t = time_based_t
        else:
            t = min(1.0, descriptor.lerp_speed * dt)

        if isinstance(current, (int, float)) and isinstance(target, (int, float)):
            new_val = current + (target - current) * t
            if abs(target - new_val) < 0.01:
                new_val = target
            setattr(obj, descriptor.attr_name, type(current)(new_val))

        elif isinstance(current, tuple) and isinstance(target, tuple):
            new_vals = []
            for c, tgt in zip(current, target):
                v = c + (tgt - c) * t
                if abs(tgt - v) < 0.01:
                    v = tgt
                new_vals.append(v)
            setattr(obj, descriptor.attr_name, tuple(new_vals))
        else:
            # Tipo non interpolabile: snap
            setattr(obj, descriptor.attr_name, target)
