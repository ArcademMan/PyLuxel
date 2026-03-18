"""pyluxel.net.peer -- Rappresentazione di un peer connesso."""

from dataclasses import dataclass, field
import time


@dataclass
class Peer:
    """Stato di connessione di un peer remoto."""
    id: int
    address: str = ""
    port: int = 0
    steam_id: int = 0
    name: str = ""
    rtt: float = 0.0
    connected_at: float = field(default_factory=time.perf_counter)
    state: str = "connecting"  # "connecting" | "connected" | "disconnected"

    @property
    def is_connected(self) -> bool:
        return self.state == "connected"

    @property
    def uptime(self) -> float:
        """Secondi dalla connessione."""
        return time.perf_counter() - self.connected_at
