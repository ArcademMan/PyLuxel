"""pyluxel.net -- Multiplayer networking per PyLuxel.

Singleton ``Net`` per gestire connessioni P2P, state sync e RPC.
Supporta UDP (dev/LAN) e Steam Networking Sockets (produzione).

Uso rapido::

    from pyluxel.net import Net

    Net.host()                    # Steam con App ID 480 (fallback UDP)
    Net.host(transport="udp")     # UDP diretto per LAN/test

    Net.join("127.0.0.1")        # Connettiti a un host
"""

from pyluxel.net.manager import NetworkManager
from pyluxel.net.node import NetNode
from pyluxel.net.peer import Peer
from pyluxel.net.rpc import rpc, RPCTarget, host_only
from pyluxel.net.sync import synced
from pyluxel.net.transport import Transport, UDPTransport, TransportEvent

Net = NetworkManager()

__all__ = [
    "NetworkManager",
    "Net",
    "NetNode",
    "Peer",
    "rpc",
    "RPCTarget",
    "host_only",
    "synced",
    "Transport",
    "UDPTransport",
    "TransportEvent",
]
