"""pyluxel.net.rpc -- Remote Procedure Call system.

Decoratore ``@rpc`` per marcare metodi come chiamabili in rete.
Il NetworkManager gestisce la serializzazione e il dispatch.
"""

import struct
from dataclasses import dataclass
from typing import Callable

from pyluxel.net.protocol import pack_values, unpack_values


class RPCTarget:
    """Target per RPC."""
    ALL = "all"         # tutti ricevono (incluso il mittente localmente)
    HOST = "host"       # solo l'host riceve
    OTHERS = "others"   # tutti tranne il mittente
    PEER = "peer"       # peer specifico (serve peer_id)


@dataclass(slots=True)
class RPCMeta:
    """Metadata di un metodo RPC."""
    name: str
    name_hash: int
    target: str
    reliable: bool


def _hash_name(name: str) -> int:
    """Hash CRC-like a 32 bit del nome."""
    h = 0
    for c in name:
        h = ((h << 5) + h + ord(c)) & 0xFFFFFFFF
    return h


def rpc(target: str = RPCTarget.ALL, reliable: bool = True):
    """Decoratore per marcare un metodo come RPC.

    Uso::

        class Player:
            @rpc(target="all")
            def take_damage(self, amount: int):
                self.health -= amount

    Quando ``player.take_damage(10)`` viene chiamato:
    1. Esegue il metodo localmente
    2. Serializza la chiamata e la invia ai peer

    Args:
        target: Chi riceve l'RPC ("all", "host", "others").
        reliable: Se True, usa canale affidabile.
    """
    def decorator(fn: Callable) -> Callable:
        name = fn.__qualname__
        meta = RPCMeta(
            name=name,
            name_hash=_hash_name(name),
            target=target,
            reliable=reliable,
        )

        def wrapper(self, *args, _rpc_remote: bool = False,
                    _rpc_peer_id: int | None = None, **kwargs):
            # Esegui localmente
            result = fn(self, *args, **kwargs)

            # Se e' una chiamata locale (non ricevuta da rete), invia
            if not _rpc_remote:
                _send_rpc(self, meta, args, peer_id=_rpc_peer_id)

            return result

        wrapper._rpc_meta = meta
        wrapper.__name__ = fn.__name__
        wrapper.__qualname__ = fn.__qualname__
        return wrapper

    return decorator


# Cache lazy per evitare import in hot path
_net_ref = None


def _get_net():
    global _net_ref
    if _net_ref is None:
        from pyluxel.net import Net
        _net_ref = Net
    return _net_ref


def host_only(fn):
    """Decoratore: il metodo viene eseguito solo se Net.is_host è True."""
    def wrapper(self, *args, **kwargs):
        net = _get_net()
        if net.is_host:
            return fn(self, *args, **kwargs)
    wrapper.__name__ = fn.__name__
    wrapper.__qualname__ = fn.__qualname__
    return wrapper


def _send_rpc(obj: object, meta: RPCMeta, args: tuple,
              peer_id: int | None = None):
    """Serializza e invia un RPC attraverso il NetworkManager."""
    Net = _get_net()

    if not Net.is_connected:
        return

    obj_id = Net._obj_to_id.get(id(obj))
    if obj_id is None:
        return  # Oggetto non registrato

    # Calcola target_peer per routing
    target = "peer" if peer_id is not None else meta.target
    if target == "peer" and peer_id is not None:
        target_peer = peer_id
    elif target == "host":
        target_peer = 0
    else:
        target_peer = -1  # broadcast (all / others)

    # Payload: [target_peer: i16] [name_hash: u32] [obj_id: u32]
    #          [name_len: u8] [name: bytes] [arg_count: u8] [args...]
    name_bytes = meta.name.encode("utf-8")
    header = struct.pack("<hIIB", target_peer, meta.name_hash,
                         obj_id, len(name_bytes))
    args_header = struct.pack("<B", len(args))
    args_data = pack_values(*args) if args else b""
    payload = header + name_bytes + args_header + args_data

    Net._send_rpc_packet(payload, target, peer_id, meta.reliable)


def dispatch_rpc(manager, peer_id: int, payload: bytes):
    """Dispatch di un RPC ricevuto dalla rete."""
    if len(payload) < 11:
        return

    from pyluxel.debug import cprint

    # [target_peer: i16] [name_hash: u32] [obj_id: u32] [name_len: u8]
    _target_peer, name_hash, obj_id, name_len = struct.unpack_from(
        "<hIIB", payload)
    offset = 11

    # Leggi il nome del metodo per verifica anti-collision
    if offset + name_len > len(payload):
        return
    rpc_name = payload[offset:offset + name_len].decode("utf-8", errors="replace")
    offset += name_len

    # Leggi arg_count
    if offset >= len(payload):
        return
    arg_count = payload[offset]
    offset += 1

    # Deserializza argomenti
    args = []
    if arg_count > 0:
        try:
            args, offset = unpack_values(payload, arg_count, offset)
        except (ValueError, struct.error):
            cprint.warning(f"Net RPC: failed to deserialize args for {rpc_name}")
            return

    entries = manager._rpc_dispatch.get(name_hash, [])
    if not entries:
        cprint.warning(f"Net RPC: no handlers for hash={name_hash:#x} ({rpc_name})")
        return

    found = False
    for entry_obj_id, method_name, obj in entries:
        if entry_obj_id == obj_id:
            # Verifica nome per evitare dispatch su hash collision
            full_name = getattr(getattr(type(obj), method_name, None),
                                "__qualname__", "")
            if full_name != rpc_name:
                cprint.warning(f"Net RPC: hash collision! expected={rpc_name} "
                               f"got={full_name}")
                continue  # Collisione: prova il prossimo handler
            found = True
            method = getattr(obj, method_name, None)
            if method:
                try:
                    method(*args, _rpc_remote=True)
                except Exception as e:
                    cprint.warning(f"Net RPC dispatch error ({method_name}): {e}")
            break

    if not found:
        cprint.warning(f"Net RPC: obj_id={obj_id} not found for {rpc_name} "
                       f"(registered: {[e[0] for e in entries]})")
