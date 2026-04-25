"""pyluxel.net.manager -- NetworkManager, il cuore del networking.

Singleton che orchestra transport, callbacks, sync e RPC.
Uso: ``from pyluxel.net import Net`` poi ``Net.host()`` / ``Net.join()``.
"""

import struct
import time
import zlib
from collections import deque
from typing import Callable

from pyluxel.debug import cprint
from pyluxel.net.peer import Peer
from pyluxel.net.protocol import (
    MsgType, pack_header, COMPRESSION_FLAG, COMPRESSION_THRESHOLD,
)
from pyluxel.net.transport import Transport, TransportEvent


class NetworkManager:
    """Gestore di rete singleton. Stile identico a InputManager/SoundManager."""

    def __init__(self):
        self._transport: Transport | None = None
        self._peers: dict[int, Peer] = {}
        self._is_host: bool = False
        self._local_id: int = 0
        self._connected: bool = False
        self._transport_kind: str = ""

        # Callbacks
        self._on_connect: list[Callable[[int], None]] = []
        self._on_disconnect: list[Callable[[int], None]] = []
        self._on_raw: list[Callable[[int, bytes], None]] = []

        # Sync
        self._registered: dict[int, object] = {}  # obj_id -> object
        self._local_objects: set[int] = set()      # obj_ids owned locally
        self._remote_objects: set[int] = set()     # obj_ids owned remotely
        self._obj_to_id: dict[int, int] = {}      # id(obj) -> obj_id
        self._sync_tick_rate: float = 1.0 / 20.0   # 20 Hz
        self._sync_accumulator: float = 0.0
        self._obj_per_owner: int = 1000           # max oggetti per owner

        # RPC dispatch: rpc_name_hash -> (obj_id, method_name)
        self._rpc_dispatch: dict[int, list[tuple[int, str, object]]] = {}
        # Cache: class type -> list of (attr_name, rpc_meta)
        self._rpc_class_cache: dict[type, list[tuple[str, object]]] = {}

        # Rate limiting per RPC relay (anti-flood)
        self._rpc_rate: dict[int, deque[float]] = {}  # peer_id -> deque[timestamps]
        self._rpc_rate_limit: int = 300  # max RPC per secondo per peer
        self._rpc_rate_window: float = 1.0  # secondi

        # Node factory — multi-type: name → (factory, auto_spawn)
        self._node_factories: dict[str, tuple[Callable, bool]] = {}
        self._nodes: dict[int, dict[str, object]] = {}  # peer_id → {type_name: node}
        self._auto_nodes: dict[int, object] = {}  # peer_id → primary auto_spawn node
        self._on_node_created: list[Callable[[int, object], None]] = []
        self._on_node_removed: list[Callable[[int, object], None]] = []

        # Context applicativo (accessibile dagli RPC)
        self._context: object | None = None

        # Network event bus
        self._event_handlers: dict[str, list[Callable]] = {}

        # Bandwidth stats
        self._bytes_sent: int = 0
        self._bytes_recv: int = 0
        self._packets_sent: int = 0
        self._packets_recv: int = 0
        self._stats_timer: float = 0.0
        self.stats_sent_bps: int = 0
        self.stats_recv_bps: int = 0
        self.stats_sent_pps: int = 0
        self.stats_recv_pps: int = 0

        # Network clock
        self._clock_offset: float = 0.0       # offset per convertire local → net time
        self._clock_samples: list[float] = []  # ultimi N offset misurati
        self._clock_sync_timer: float = 0.0
        self._clock_synced: bool = False

        # Lobby
        self._lobby = None

        # Configurazione transport
        self._steam_enabled: bool = True
        self._default_transport: str = "steam"

    # ------------------------------------------------------------------
    # Configurazione
    # ------------------------------------------------------------------

    def configure(self, *, steam: bool = True,
                  default_transport: str | None = None) -> None:
        """Configura globalmente il networking.

        Chiamare prima di host/join/init. Idempotente.

        Args:
            steam: Se False, disabilita Steam: ``transport="steam"`` lancia
                RuntimeError e la DLL non viene mai caricata. Default True.
            default_transport: Transport usato da host/join/init quando
                l'utente non passa ``transport=`` esplicito. Se None, viene
                dedotto: ``"steam"`` se ``steam=True``, altrimenti ``"udp"``.
        """
        self._steam_enabled = steam
        if default_transport is not None:
            if not steam and default_transport == "steam":
                cprint.warning(
                    "Net.configure: default_transport='steam' incoerente con "
                    "steam=False. Forzo a 'udp'."
                )
                self._default_transport = "udp"
            else:
                self._default_transport = default_transport
        elif not steam and self._default_transport == "steam":
            self._default_transport = "udp"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def init(self, *, transport: str | None = None, app_id: int = 480) -> None:
        """Inizializza il transport senza connettersi.

        Utile per avere ``local_name`` disponibile prima di host/join.
        Se il transport e' gia' creato, non fa nulla.
        """
        if self._transport is not None:
            return
        kind = transport if transport is not None else self._default_transport
        self._transport = self._create_transport(kind, app_id)
        self._transport_kind = kind
        # Forza l'init immediato (es. Steam) cosi' local_name e' disponibile
        if hasattr(self._transport, "_init_steam"):
            self._transport._init_steam()

    def host(self, port: int = 7777, *, transport: str | None = None,
             app_id: int = 480) -> None:
        """Avvia come host.

        Args:
            port: Porta UDP (ignorata con Steam).
            transport: "steam" o "udp". Se None, usa il default configurato
                via :meth:`configure` (default ``"steam"``).
            app_id: Steam App ID (default 480 = Spacewar).
        """
        if self._connected:
            cprint.warning("Net: gia' connesso, disconnetti prima.")
            return

        kind = transport if transport is not None else self._default_transport
        if self._transport is None:
            self._transport = self._create_transport(kind, app_id)
        self._transport.listen(port)
        self._is_host = True
        self._local_id = 0  # host e' sempre 0
        self._connected = True
        self._transport_kind = kind
        cprint.info(f"Net: hosting su porta {port} ({kind})")

        # Auto-create nodo locale se factory registrata
        self._auto_create_node(self._local_id)

    def join(self, address: str = "127.0.0.1", port: int = 7777, *,
             transport: str | None = None, app_id: int = 480) -> None:
        """Connettiti a un host.

        Args:
            address: IP dell'host.
            port: Porta UDP.
            transport: "steam" o "udp". Se None, usa il default configurato
                via :meth:`configure` (default ``"steam"``).
            app_id: Steam App ID.
        """
        if self._connected:
            cprint.warning("Net: gia' connesso, disconnetti prima.")
            return

        kind = transport if transport is not None else self._default_transport
        if self._transport is None:
            self._transport = self._create_transport(kind, app_id)
        self._transport.connect(address, port)
        self._is_host = False
        self._connected = True
        self._transport_kind = kind
        cprint.info(f"Net: connessione a {address}:{port} ({kind})")

    def disconnect(self) -> None:
        """Disconnetti e chiudi il transport."""
        # Notifica disconnessione PRIMA di chiudere il transport
        # (i callback potrebbero aver bisogno di inviare dati)
        for pid in list(self._peers.keys()):
            for cb in self._on_disconnect:
                try:
                    cb(pid)
                except Exception as e:
                    cprint.warning(f"Net disconnect callback error: {e}")

        if self._transport:
            self._transport.close()
            self._transport = None

        self._peers.clear()
        self._connected = False
        self._is_host = False
        self._registered.clear()
        self._local_objects.clear()
        self._remote_objects.clear()
        self._obj_to_id.clear()
        self._rpc_dispatch.clear()
        self._rpc_rate.clear()
        self._rpc_class_cache.clear()
        # NOTA: _event_handlers, _on_connect, _on_disconnect, _on_node_created,
        # _on_node_removed, _on_raw, _node_factories sopravvivono al disconnect
        # cosi' un re-host/re-join funziona senza ri-registrare tutto.
        self._nodes.clear()
        self._auto_nodes.clear()
        self._bytes_sent = 0
        self._bytes_recv = 0
        self._packets_sent = 0
        self._packets_recv = 0
        self._stats_timer = 0.0
        self.stats_sent_bps = 0
        self.stats_recv_bps = 0
        self.stats_sent_pps = 0
        self.stats_recv_pps = 0
        self._clock_offset = 0.0
        self._clock_samples.clear()
        self._clock_sync_timer = 0.0
        self._clock_synced = False
        # Pulisci cache module-level in sync.py
        from pyluxel.net.sync import clear_sync_caches
        clear_sync_caches()
        cprint.info("Net: disconnesso.")

    def poll(self, dt: float = 0.0) -> None:
        """Processa pacchetti in arrivo. Chiamare ogni frame.

        Args:
            dt: Delta time per interpolazione sync. Se 0, usa perf_counter.
        """
        if self._transport is None:
            return

        events = self._transport.poll()
        for event in events:
            if event.type == "data" and event.data:
                self._bytes_recv += len(event.data)
                self._packets_recv += 1
            self._handle_event(event)

        # Update peer RTT from transport
        if hasattr(self._transport, "get_peer_rtt"):
            for pid, peer in self._peers.items():
                peer.rtt = self._transport.get_peer_rtt(pid)

        # Sync tick
        if dt <= 0:
            dt = 0.016  # fallback ~60fps
        self._sync_accumulator += dt
        if self._sync_accumulator >= self._sync_tick_rate:
            self._sync_accumulator -= self._sync_tick_rate
            self._flush_sync()

        # Aggiorna interpolazione oggetti remoti
        self._update_interpolation(dt)

        # Clock sync: host invia TIME_SYNC ogni 2 secondi
        self._clock_sync_timer += dt
        if self._is_host and self._clock_sync_timer >= 2.0:
            self._clock_sync_timer -= 2.0
            self._send_time_sync()

        # Stats: calcola bps/pps ogni secondo
        self._stats_timer += dt
        if self._stats_timer >= 1.0:
            self.stats_sent_bps = self._bytes_sent
            self.stats_recv_bps = self._bytes_recv
            self.stats_sent_pps = self._packets_sent
            self.stats_recv_pps = self._packets_recv
            self._bytes_sent = 0
            self._bytes_recv = 0
            self._packets_sent = 0
            self._packets_recv = 0
            self._stats_timer -= 1.0

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_connect(self, fn: Callable[[int], None]) -> Callable:
        """Registra callback per nuove connessioni. Riceve peer_id."""
        self._on_connect.append(fn)
        return fn

    def on_disconnect(self, fn: Callable[[int], None]) -> Callable:
        """Registra callback per disconnessioni. Riceve peer_id."""
        self._on_disconnect.append(fn)
        return fn

    def on_raw(self, fn: Callable[[int, bytes], None]) -> Callable:
        """Registra callback per dati raw. Riceve (peer_id, bytes)."""
        self._on_raw.append(fn)
        return fn

    # ------------------------------------------------------------------
    # Network events
    # ------------------------------------------------------------------

    def on_event(self, event_name: str):
        """Decoratore per ricevere eventi di rete.

        Uso::

            @Net.on_event("explosion")
            def on_explosion(peer_id, x, y, radius):
                spawn_particles(x, y, radius)
        """
        def decorator(fn):
            self._event_handlers.setdefault(event_name, []).append(fn)
            return fn
        return decorator

    def emit(self, event_name: str, *args, reliable: bool = True):
        """Emette un evento di rete a tutti i peer.

        Esegue i handler locali e invia l'evento ai peer remoti.

        Uso::

            Net.emit("explosion", x, y, radius)
            Net.emit("footstep", x, y, reliable=False)
        """
        self._emit_internal(event_name, args, target_peer=-1,
                            reliable=reliable)

    def emit_to(self, peer_id: int, event_name: str, *args,
                reliable: bool = True):
        """Emette un evento di rete a un peer specifico.

        In topologia star, il client invia all'host che inoltra al destinatario.

        Uso::

            Net.emit_to(peer_id, "private_msg", "ciao")
        """
        self._emit_internal(event_name, args, target_peer=peer_id,
                            reliable=reliable)

    def emit_to_host(self, event_name: str, *args, reliable: bool = True):
        """Emette un evento solo all'host (peer 0).

        Uso::

            Net.emit_to_host("buy_item", item_id)
        """
        self._emit_internal(event_name, args, target_peer=0,
                            reliable=reliable)

    def emit_to_client(self, peer_id: int, event_name: str, *args,
                       reliable: bool = True):
        """Emette un evento a un client specifico (non accetta peer 0 / host).

        Uso dall'host::

            Net.emit_to_client(peer_id, "loot_drop", item_id, x, y)
        """
        if peer_id == 0:
            cprint.warning("Net: emit_to_client non accetta peer_id=0 (host). "
                           "Usa emit_to_host().")
            return
        self._emit_internal(event_name, args, target_peer=peer_id,
                            reliable=reliable)

    def _emit_internal(self, event_name: str, args: tuple,
                       target_peer: int, reliable: bool):
        """Logica condivisa per emit/emit_to."""
        # Esegui localmente (se broadcast o se il target siamo noi)
        if target_peer < 0 or target_peer == self._local_id:
            for cb in self._event_handlers.get(event_name, []):
                try:
                    cb(self._local_id, *args)
                except Exception as e:
                    cprint.warning(f"Net event '{event_name}' error: {e}")

        if not self._transport or not self._connected:
            return

        from pyluxel.net.protocol import pack_values
        name_bytes = event_name.encode("utf-8")
        # Payload: [target_peer: i16] [name_len: u8] [name] [arg_count: u8] [args...]
        payload = struct.pack("<hB", target_peer, len(name_bytes)) + name_bytes
        payload += struct.pack("<B", len(args))
        if args:
            payload += pack_values(*args)

        msg = self._compress_msg(MsgType.NET_EVENT, payload)
        if target_peer >= 0 and target_peer != self._local_id:
            # Mirato: se siamo host, invia diretto. Se client, invia all'host per relay.
            if self._is_host:
                self._transport.send(target_peer, msg, reliable)
            else:
                self._transport.send(0, msg, reliable)
        else:
            self._transport.send_all(msg, reliable)
        self._bytes_sent += len(msg)
        self._packets_sent += 1

    # ------------------------------------------------------------------
    # Node factory (auto-create NetNode per peer)
    # ------------------------------------------------------------------

    def register_node_type(self, name_or_factory, factory=None, *,
                           auto_spawn: bool = False):
        """Registra una factory per creare nodi sincronizzati.

        Supporta due forme:

        Legacy (backward compat)::

            Net.register_node_type(NetPlayer)  # auto_spawn=True

        Multi-type::

            Net.register_node_type("Bullet", BulletNode)
            Net.register_node_type("PowerUp", PowerUpNode, auto_spawn=True)
        """
        if factory is None:
            # Legacy: Net.register_node_type(NetPlayer)
            factory = name_or_factory
            name = factory.__name__
            auto_spawn = True
        else:
            name = name_or_factory
        self._node_factories[name] = (factory, auto_spawn)

    def on_node_created(self, fn: Callable[[int, object], None]):
        """Callback: (peer_id, node) — chiamato quando un nodo è creato."""
        self._on_node_created.append(fn)
        return fn

    def on_node_removed(self, fn: Callable[[int, object], None]):
        """Callback: (peer_id, node) — chiamato quando un nodo è rimosso."""
        self._on_node_removed.append(fn)
        return fn

    def get_node(self, peer_id: int, type_name: str | None = None) -> object | None:
        """Ritorna il NetNode di un peer, o None.

        Se type_name è specificato, ritorna solo quel tipo.
        Altrimenti ritorna il primo auto_spawn (backward compat).
        """
        peer_nodes = self._nodes.get(peer_id)
        if peer_nodes is None:
            return None
        if type_name:
            return peer_nodes.get(type_name)
        # Backward compat: ritorna il primo auto_spawn
        for tname, node in peer_nodes.items():
            info = self._node_factories.get(tname)
            if info and info[1]:  # auto_spawn
                return node
        return next(iter(peer_nodes.values()), None) if peer_nodes else None

    @property
    def nodes(self) -> dict[int, object]:
        """Dizionario live peer_id → nodo auto_spawn primario.

        Mantenuto automaticamente dall'engine: si popola quando un peer
        si connette e si svuota quando si disconnette o si chiama disconnect().
        I giochi possono usare direttamente ``Net.nodes`` come player dict
        senza dover scrivere callback on_node_created/on_node_removed
        per tenerne traccia.
        """
        return self._auto_nodes

    # ------------------------------------------------------------------
    # Spawn / Despawn
    # ------------------------------------------------------------------

    def spawn(self, type_name: str, **init_kwargs) -> object:
        """Spawn un nodo sincronizzato, replicato a tutti i peer.

        Args:
            type_name: Nome registrato via register_node_type.
            **init_kwargs: Argomenti extra passati alla factory.

        Returns:
            Il nodo creato localmente.
        """
        factory, _ = self._node_factories[type_name]
        node = factory(owner=self._local_id, **init_kwargs)
        node._net_type_name = type_name
        obj_id = self.register(node)
        self._nodes.setdefault(self._local_id, {})[type_name] = node
        self._send_spawn(type_name, self._local_id, obj_id)
        for cb in self._on_node_created:
            try:
                cb(self._local_id, node)
            except Exception as e:
                cprint.warning(f"Net on_node_created error: {e}")
        return node

    def despawn(self, node: object) -> None:
        """Rimuovi un nodo sincronizzato, replicato a tutti i peer."""
        obj_id = self._obj_to_id.get(id(node))
        if obj_id is None:
            return
        self._send_despawn(obj_id)
        self.unregister(node)
        # Rimuovi da _nodes
        owner = getattr(node, "_net_owner", -1)
        type_name = getattr(node, "_net_type_name", "")
        peer_nodes = self._nodes.get(owner)
        if peer_nodes and type_name in peer_nodes:
            del peer_nodes[type_name]
            if not peer_nodes:
                del self._nodes[owner]
        for cb in self._on_node_removed:
            try:
                cb(owner, node)
            except Exception as e:
                cprint.warning(f"Net on_node_removed error: {e}")

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------

    @property
    def context(self) -> object | None:
        """Contesto applicativo accessibile dagli RPC."""
        return self._context

    @context.setter
    def context(self, value):
        self._context = value

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    def send(self, peer_id: int, data: bytes, *, reliable: bool = True) -> None:
        """Invia dati raw a un peer specifico."""
        if self._transport is None:
            return
        payload = struct.pack("<B", MsgType.RAW_DATA) + data
        self._transport.send(peer_id, payload, reliable)

    def send_all(self, data: bytes, *, reliable: bool = True,
                 exclude: int | None = None) -> None:
        """Invia dati raw a tutti i peer connessi."""
        if self._transport is None:
            return
        payload = struct.pack("<B", MsgType.RAW_DATA) + data
        self._transport.send_all(payload, reliable, exclude)

    # ------------------------------------------------------------------
    # Object registration (per sync + RPC)
    # ------------------------------------------------------------------

    def register(self, obj: object) -> int:
        """Registra un oggetto per sync automatico e RPC.

        L'oggetto deve avere ``_net_owner`` (int, peer_id proprietario).
        L'obj_id e' deterministico (basato su _net_owner) cosi' entrambi
        i peer usano lo stesso ID per lo stesso oggetto.
        Ritorna l'obj_id assegnato.
        """
        owner = getattr(obj, "_net_owner", self._local_id)
        # ID deterministico: owner 0 → obj_id 1..N, owner 1 → N+1..2N, ecc.
        cap = self._obj_per_owner
        base = owner * cap + 1
        limit = base + cap
        obj_id = base
        while obj_id in self._registered:
            obj_id += 1
        if obj_id >= limit:
            raise RuntimeError(
                f"Net: limite di {cap} oggetti per owner raggiunto "
                f"(owner={owner}). Usa Net.obj_per_owner per aumentarlo."
            )
        self._registered[obj_id] = obj
        self._obj_to_id[id(obj)] = obj_id

        # Traccia per ownership (evita O(n) scan in flush/interpolation)
        if owner == self._local_id:
            self._local_objects.add(obj_id)
        else:
            self._remote_objects.add(obj_id)

        cprint.info(f"Net: register obj_id={obj_id} owner={owner} "
                    f"type={type(obj).__name__}")

        # Init sync metadata
        if not hasattr(obj, "_net_dirty"):
            obj._net_dirty = set()
        if not hasattr(obj, "_net_owner"):
            obj._net_owner = self._local_id

        # Registra RPC methods (cached per classe)
        cls = type(obj)
        rpc_methods = self._rpc_class_cache.get(cls)
        if rpc_methods is None:
            rpc_methods = []
            for attr_name in dir(cls):
                attr = getattr(cls, attr_name, None)
                if attr and hasattr(attr, "_rpc_meta"):
                    rpc_methods.append((attr_name, attr._rpc_meta))
            self._rpc_class_cache[cls] = rpc_methods

        for attr_name, meta in rpc_methods:
            entry = (obj_id, attr_name, obj)
            self._rpc_dispatch.setdefault(meta.name_hash, []).append(entry)

        # Invia stato completo ai peer (full sync)
        self._send_full_sync(obj_id, obj)

        return obj_id

    def register_with_id(self, obj: object, obj_id: int) -> int:
        """Register an object with a specific obj_id for sync and RPC.

        Use for manually registered objects that need deterministic IDs
        independent of registration order. The caller must ensure obj_id
        doesn't collide with auto-assigned IDs.
        """
        if obj_id in self._registered:
            raise ValueError(f"Net: obj_id={obj_id} already registered")
        return self._register_with_id(obj, obj_id)

    def unregister(self, obj: object) -> None:
        """Rimuovi un oggetto dal sync/RPC."""
        if obj is None:
            return
        py_id = id(obj)
        obj_id = self._obj_to_id.pop(py_id, None)
        if obj_id is not None:
            self._registered.pop(obj_id, None)
            self._local_objects.discard(obj_id)
            self._remote_objects.discard(obj_id)
            # Rimuovi da RPC dispatch (usa cache per trovare solo gli hash rilevanti)
            cls = type(obj)
            rpc_methods = self._rpc_class_cache.get(cls, [])
            for _, meta in rpc_methods:
                entries = self._rpc_dispatch.get(meta.name_hash)
                if entries:
                    self._rpc_dispatch[meta.name_hash] = [
                        e for e in entries if e[0] != obj_id
                    ]

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def steam_enabled(self) -> bool:
        """True se Steam e' abilitato (default). Vedi :meth:`configure`."""
        return self._steam_enabled

    @property
    def default_transport(self) -> str:
        """Transport usato di default da host/join/init. Vedi :meth:`configure`."""
        return self._default_transport

    @property
    def is_host(self) -> bool:
        return self._is_host

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def local_id(self) -> int:
        return self._local_id

    @property
    def local_name(self) -> str:
        """Nome del giocatore locale (Steam). Stringa vuota se non Steam."""
        if self._transport and hasattr(self._transport, "get_local_name"):
            return self._transport.get_local_name()
        return ""

    @property
    def peer_count(self) -> int:
        return len(self._peers)

    @property
    def peers(self) -> list[int]:
        return list(self._peers.keys())

    def get_peer(self, peer_id: int) -> Peer | None:
        return self._peers.get(peer_id)

    def get_player_name(self, peer_id: int) -> str:
        """Ritorna il nome di un peer. Usa Steam se disponibile."""
        peer = self._peers.get(peer_id)
        if peer is None:
            return ""
        return peer.name

    def check_launch_invite(self) -> bool:
        """Controlla se il gioco e' stato lanciato da un invito Steam.

        Se trova ``+connect_lobby <id>`` in sys.argv, si connette
        automaticamente alla lobby. Ritorna True se un join e' in corso.

        Chiamare dopo l'init del gioco, prima del loop principale.
        """
        lobby_id = self.lobby.check_launch_args()
        if lobby_id:
            cprint.info(f"Net: invito Steam rilevato, joining lobby {lobby_id}")
            self.lobby.join_code(lobby_id)
            return True
        return False

    @property
    def lobby(self):
        """Accesso al LobbyManager (lazy init)."""
        if self._lobby is None:
            from pyluxel.net.lobby import LobbyManager
            self._lobby = LobbyManager(self)
        return self._lobby

    @property
    def sync_tick_rate(self) -> float:
        """Tick rate di sync in Hz."""
        return 1.0 / self._sync_tick_rate

    @sync_tick_rate.setter
    def sync_tick_rate(self, hz: float):
        """Imposta il tick rate di sync (default 20 Hz)."""
        self._sync_tick_rate = 1.0 / max(1.0, hz)

    @property
    def rpc_rate_limit(self) -> int:
        """Max RPC relay per peer al secondo (default 300). 0 = nessun limite."""
        return self._rpc_rate_limit

    @rpc_rate_limit.setter
    def rpc_rate_limit(self, value: int):
        self._rpc_rate_limit = max(0, value)

    @property
    def obj_per_owner(self) -> int:
        """Max oggetti registrabili per owner (default 1000).

        Impostare PRIMA di host/join. Deve essere uguale su tutti i peer.
        """
        return self._obj_per_owner

    @obj_per_owner.setter
    def obj_per_owner(self, value: int):
        self._obj_per_owner = max(1, value)

    @property
    def stats(self) -> dict:
        """Statistiche di rete correnti."""
        return {
            "sent_bps": self.stats_sent_bps,
            "recv_bps": self.stats_recv_bps,
            "sent_pps": self.stats_sent_pps,
            "recv_pps": self.stats_recv_pps,
            "peers": self.peer_count,
        }

    @property
    def net_time(self) -> float:
        """Tempo di rete sincronizzato (secondi).

        Sull'host coincide con perf_counter(). Sui client e' allineato
        al clock dell'host tramite TIME_SYNC + RTT/2.
        """
        return time.perf_counter() + self._clock_offset

    @property
    def clock_offset(self) -> float:
        """Offset tra clock locale e clock dell'host (secondi)."""
        return self._clock_offset

    @property
    def clock_synced(self) -> bool:
        """True se il clock e' stato sincronizzato almeno una volta."""
        return self._clock_synced

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _create_transport(self, kind: str, app_id: int) -> Transport:
        """Crea il transport richiesto con fallback."""
        if kind == "udp":
            from pyluxel.net.transport import UDPTransport
            return UDPTransport()

        if kind == "steam":
            if not self._steam_enabled:
                raise RuntimeError(
                    "Net: Steam transport disabilitato via Net.configure(steam=False). "
                    "Usa un transport diverso (es. 'udp') o riabilita Steam."
                )
            try:
                from pyluxel.net.transport_steam import SteamTransport
                return SteamTransport(app_id=app_id)
            except ImportError:
                cprint.warning(
                    "Net: Steam transport non disponibile, fallback a UDP. "
                    "Assicurati che steam_api64.dll sia nella directory del gioco."
                )
                from pyluxel.net.transport import UDPTransport
                return UDPTransport()

        raise ValueError(f"Transport sconosciuto: {kind!r}. Usa 'udp' o 'steam'.")

    def _handle_event(self, event: TransportEvent):
        """Processa un evento dal transport."""
        if event.type == "connect":
            peer = Peer(id=event.peer_id)
            peer.address = event.address
            peer.port = event.port
            peer.state = "connected"

            # Popola steam_id e nome se usiamo Steam transport
            if self._transport and hasattr(self._transport, "get_player_name"):
                steam_peers = getattr(self._transport, "_peers", {})
                sid = steam_peers.get(event.peer_id, 0)
                if sid:
                    peer.steam_id = sid
                    peer.name = self._transport.get_player_name(sid)

            self._peers[event.peer_id] = peer

            # Se siamo client, aggiorna local_id dal transport
            if not self._is_host and hasattr(self._transport, "local_id"):
                self._local_id = self._transport.local_id
                # Auto-create nodo locale (client, primo connect)
                self._auto_create_node(self._local_id)

            # Auto-create nodo per il nuovo peer
            self._auto_create_node(event.peer_id)

            # Host: invia PEER_LIST a TUTTI i peer (nuovo + esistenti)
            # così anche i peer già connessi creano il nodo del nuovo arrivato
            if self._is_host and self._node_factories and self._transport:
                for pid in list(self._peers.keys()):
                    self._send_peer_list(pid)

            # Invia stato corrente di tutti i nostri oggetti al nuovo peer
            self._send_state_to_peer(event.peer_id)

            for cb in self._on_connect:
                try:
                    cb(event.peer_id)
                except Exception as e:
                    cprint.warning(f"Net on_connect error: {e}")

        elif event.type == "disconnect":
            # Rimuovi nodo del peer disconnesso
            self._auto_remove_node(event.peer_id)

            self._peers.pop(event.peer_id, None)
            for cb in self._on_disconnect:
                try:
                    cb(event.peer_id)
                except Exception as e:
                    cprint.warning(f"Net on_disconnect error: {e}")

        elif event.type == "data" and event.data:
            self._handle_data(event.peer_id, event.data)

    def _handle_data(self, peer_id: int, data: bytes):
        """Dispatch dati ricevuti in base al tipo."""
        if len(data) < 1:
            return

        msg_type = data[0]
        payload = data[1:]

        # Decompressione: se bit 7 è impostato, il payload è zlib-compresso
        if msg_type & COMPRESSION_FLAG:
            msg_type = msg_type & ~COMPRESSION_FLAG
            try:
                payload = zlib.decompress(payload)
            except zlib.error:
                cprint.warning(f"Net: zlib decompression failed from peer={peer_id}")
                return

        if msg_type == MsgType.STATE_SYNC:
            # Host: valida ownership prima di applicare e fare relay
            if self._is_host and len(payload) >= 4:
                obj_id = struct.unpack_from("<I", payload)[0]
                obj = self._registered.get(obj_id)
                if obj and getattr(obj, "_net_owner", -1) != peer_id:
                    cprint.warning(
                        f"Net: rejected STATE_SYNC from peer={peer_id} "
                        f"for obj_id={obj_id} (owner="
                        f"{getattr(obj, '_net_owner', -1)})")
                    return
            self._handle_sync(peer_id, payload)
            # Host relay: inoltra sync di un client a tutti gli altri
            if self._is_host and self._transport:
                self._transport.send_all(data, reliable=False, exclude=peer_id)
        elif msg_type == MsgType.RPC_CALL:
            self._handle_rpc(peer_id, payload)
            # Host relay con rate limiting e routing mirato
            if self._is_host and self._transport:
                if not self._check_rpc_rate(peer_id):
                    cprint.warning(f"Net: RPC rate limit exceeded for peer={peer_id}")
                elif len(payload) >= 2:
                    target_peer = struct.unpack_from("<h", payload)[0]
                    if target_peer >= 0:
                        # Mirato: inoltra solo al destinatario
                        if target_peer != self._local_id:
                            self._transport.send(target_peer, data, reliable=True)
                    else:
                        # Broadcast: inoltra a tutti tranne il mittente
                        self._transport.send_all(data, reliable=True, exclude=peer_id)
        elif msg_type == MsgType.PEER_LIST:
            self._handle_peer_list(payload)
        elif msg_type == MsgType.SPAWN_NODE:
            # Host: valida che il peer spawni solo nodi propri
            if self._is_host and len(payload) >= 9:
                _, owner, _ = struct.unpack_from("<BII", payload)
                if owner != peer_id:
                    cprint.warning(
                        f"Net: rejected SPAWN_NODE from peer={peer_id} "
                        f"(claimed owner={owner})")
                    return
            self._handle_spawn(peer_id, payload)
            # Host relay
            if self._is_host and self._transport:
                self._transport.send_all(data, reliable=True, exclude=peer_id)
        elif msg_type == MsgType.DESPAWN_NODE:
            # Host: valida che il peer despawni solo i propri oggetti
            if self._is_host and len(payload) >= 4:
                obj_id = struct.unpack_from("<I", payload)[0]
                obj = self._registered.get(obj_id)
                if obj and getattr(obj, "_net_owner", -1) != peer_id:
                    cprint.warning(
                        f"Net: rejected DESPAWN_NODE from peer={peer_id} "
                        f"for obj_id={obj_id} (owner="
                        f"{getattr(obj, '_net_owner', -1)})")
                    return
            self._handle_despawn(peer_id, payload)
            # Host relay
            if self._is_host and self._transport:
                self._transport.send_all(data, reliable=True, exclude=peer_id)
        elif msg_type == MsgType.NET_EVENT:
            self._handle_net_event(peer_id, payload)
            # Host relay: leggi target_peer per routing mirato
            if self._is_host and self._transport and len(payload) >= 2:
                target_peer = struct.unpack_from("<h", payload)[0]
                if target_peer >= 0:
                    # Mirato: inoltra solo al destinatario (se non siamo noi)
                    if target_peer != self._local_id:
                        self._transport.send(target_peer, data, reliable=True)
                else:
                    # Broadcast: inoltra a tutti tranne il mittente
                    self._transport.send_all(data, reliable=True, exclude=peer_id)
        elif msg_type == MsgType.TIME_SYNC:
            self._handle_time_sync(peer_id, payload)
        elif msg_type == MsgType.RAW_DATA:
            for cb in self._on_raw:
                try:
                    cb(peer_id, payload)
                except Exception as e:
                    cprint.warning(f"Net on_raw error: {e}")

    def _handle_sync(self, peer_id: int, payload: bytes):
        """Processa un pacchetto STATE_SYNC."""
        from pyluxel.net.sync import apply_sync_packet
        apply_sync_packet(self, peer_id, payload)

    def _handle_rpc(self, peer_id: int, payload: bytes):
        """Processa un pacchetto RPC_CALL."""
        from pyluxel.net.rpc import dispatch_rpc
        dispatch_rpc(self, peer_id, payload)

    def _flush_sync(self):
        """Invia lo stato dirty di tutti gli oggetti registrati.

        Separa i campi dirty in reliable e unreliable in base al flag
        ``synced(reliable=True)``, e invia due pacchetti distinti.
        """
        from pyluxel.net.sync import build_sync_packet, _get_sync_fields

        now = self.net_time

        for obj_id in self._local_objects:
            obj = self._registered.get(obj_id)
            if obj is None:
                continue

            dirty = getattr(obj, "_net_dirty", None)
            if not dirty:
                continue

            # Split dirty in reliable / unreliable
            fields = _get_sync_fields(obj)
            reliable_dirty = {n for n in dirty if n in fields and fields[n].reliable}
            unreliable_dirty = dirty - reliable_dirty

            if unreliable_dirty:
                packet = build_sync_packet(obj_id, obj, unreliable_dirty,
                                           net_time=now)
                if packet and self._transport:
                    msg = self._compress_msg(MsgType.STATE_SYNC, packet)
                    self._transport.send_all(msg, reliable=False)
                    self._bytes_sent += len(msg)
                    self._packets_sent += 1

            if reliable_dirty:
                packet = build_sync_packet(obj_id, obj, reliable_dirty,
                                           net_time=now)
                if packet and self._transport:
                    msg = self._compress_msg(MsgType.STATE_SYNC, packet)
                    self._transport.send_all(msg, reliable=True)
                    self._bytes_sent += len(msg)
                    self._packets_sent += 1

            obj._net_dirty.clear()

    def _send_full_sync(self, obj_id: int, obj: object):
        """Invia lo stato completo di un oggetto (per nuovi peer).

        Solo il proprietario dell'oggetto puo' inviare il full sync,
        altrimenti un peer potrebbe sovrascrivere lo stato altrui con dati vuoti.
        """
        owner = getattr(obj, "_net_owner", -1)
        if owner != self._local_id:
            return  # Non sei il proprietario, non inviare

        from pyluxel.net.sync import build_full_sync_packet

        packet = build_full_sync_packet(obj_id, obj, net_time=self.net_time)
        if packet and self._transport:
            msg = self._compress_msg(MsgType.STATE_SYNC, packet)
            self._transport.send_all(msg, reliable=True)
            self._bytes_sent += len(msg)
            self._packets_sent += 1

    def _send_state_to_peer(self, peer_id: int):
        """Invia lo stato corrente di TUTTI gli oggetti registrati a un peer.

        L'host ha lo stato aggiornato di tutti gli oggetti (ricevuto via
        sync dai client), quindi puo' inoltrare lo stato completo al
        nuovo arrivato — non solo i propri oggetti.
        """
        from pyluxel.net.sync import build_full_sync_packet

        now = self.net_time
        for obj_id, obj in self._registered.items():
            packet = build_full_sync_packet(obj_id, obj, net_time=now)
            if packet and self._transport:
                msg = self._compress_msg(MsgType.STATE_SYNC, packet)
                self._transport.send(peer_id, msg, reliable=True)
                self._bytes_sent += len(msg)
                self._packets_sent += 1

    def _update_interpolation(self, dt: float):
        """Aggiorna interpolazione per oggetti remoti."""
        from pyluxel.net.sync import update_interpolation

        now = self.net_time
        for obj_id in self._remote_objects:
            obj = self._registered.get(obj_id)
            if obj is None:
                continue
            update_interpolation(obj, dt, net_time=now)

    def _check_rpc_rate(self, peer_id: int) -> bool:
        """Controlla rate limiting RPC per un peer. Ritorna True se consentito."""
        now = time.perf_counter()
        timestamps = self._rpc_rate.get(peer_id)
        if timestamps is None:
            timestamps = deque()
            self._rpc_rate[peer_id] = timestamps

        # Rimuovi timestamp vecchi (O(1) per pop con deque)
        cutoff = now - self._rpc_rate_window
        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()

        if self._rpc_rate_limit > 0 and len(timestamps) >= self._rpc_rate_limit:
            return False

        timestamps.append(now)
        return True

    # ------------------------------------------------------------------
    # Network events (internal)
    # ------------------------------------------------------------------

    def _handle_net_event(self, peer_id: int, payload: bytes):
        """Dispatch di un NET_EVENT ricevuto dalla rete."""
        if len(payload) < 4:
            return

        from pyluxel.net.protocol import unpack_values

        # [target_peer: i16] [name_len: u8] [name] [arg_count: u8] [args...]
        target_peer, name_len = struct.unpack_from("<hB", payload)
        offset = 3
        if offset + name_len > len(payload):
            return
        event_name = payload[offset:offset + name_len].decode("utf-8", errors="replace")
        offset += name_len

        if offset >= len(payload):
            return
        arg_count = payload[offset]
        offset += 1

        args = []
        if arg_count > 0:
            try:
                args, offset = unpack_values(payload, arg_count, offset)
            except (ValueError, struct.error):
                cprint.warning(f"Net: failed to deserialize event '{event_name}'")
                return

        for cb in self._event_handlers.get(event_name, []):
            try:
                cb(peer_id, *args)
            except Exception as e:
                cprint.warning(f"Net event '{event_name}' error: {e}")

    # ------------------------------------------------------------------
    # Clock sync
    # ------------------------------------------------------------------

    _CLOCK_SAMPLES = 8  # numero di campioni per la mediana

    def _send_time_sync(self):
        """Host invia il suo timestamp a tutti i client."""
        if not self._transport:
            return
        host_time = time.perf_counter()
        payload = struct.pack("<d", host_time)
        msg = struct.pack("<B", MsgType.TIME_SYNC) + payload
        self._transport.send_all(msg, reliable=False)

    def _handle_time_sync(self, peer_id: int, payload: bytes):
        """Client riceve TIME_SYNC dall'host e aggiorna l'offset."""
        if self._is_host or len(payload) < 8:
            return

        host_time = struct.unpack_from("<d", payload)[0]
        local_time = time.perf_counter()

        # Stima RTT dal peer object
        peer = self._peers.get(0)  # host e' peer 0 per il client
        rtt = peer.rtt if peer else 0.0

        # Offset = host_time + rtt/2 - local_time
        # (il pacchetto e' stato inviato ~rtt/2 fa)
        offset = host_time + rtt / 2.0 - local_time

        # Accumula campioni e usa la mediana (resistente a spike di latenza)
        self._clock_samples.append(offset)
        if len(self._clock_samples) > self._CLOCK_SAMPLES:
            self._clock_samples.pop(0)

        sorted_samples = sorted(self._clock_samples)
        self._clock_offset = sorted_samples[len(sorted_samples) // 2]
        self._clock_synced = True

    def _auto_create_node(self, peer_id: int):
        """Crea automaticamente nodi auto_spawn per un peer."""
        if not self._node_factories:
            return
        for tname, (factory, auto_spawn) in self._node_factories.items():
            if not auto_spawn:
                continue
            peer_nodes = self._nodes.get(peer_id, {})
            if tname in peer_nodes:
                continue  # Gia' creato
            node = factory(owner=peer_id)
            node._net_type_name = tname
            self._nodes.setdefault(peer_id, {})[tname] = node
            # Primo auto_spawn → inserisci nel dict flat
            if peer_id not in self._auto_nodes:
                self._auto_nodes[peer_id] = node
            self.register(node)
            cprint.info(f"Net: auto-created {tname} for peer_id={peer_id}")
            for cb in self._on_node_created:
                try:
                    cb(peer_id, node)
                except Exception as e:
                    cprint.warning(f"Net on_node_created error: {e}")

    def _auto_remove_node(self, peer_id: int):
        """Rimuove tutti i nodi di un peer disconnesso."""
        self._auto_nodes.pop(peer_id, None)
        peer_nodes = self._nodes.pop(peer_id, None)
        if peer_nodes is None:
            return
        for tname, node in peer_nodes.items():
            self.unregister(node)
            cprint.info(f"Net: auto-removed {tname} for peer_id={peer_id}")
            for cb in self._on_node_removed:
                try:
                    cb(peer_id, node)
                except Exception as e:
                    cprint.warning(f"Net on_node_removed error: {e}")

    def _send_peer_list(self, to_peer_id: int):
        """Host invia la lista di tutti i nodi esistenti al nuovo peer.

        Formato v2: [count:u16] per nodo: [name_len:u8] [owner:u32] [obj_id:u32] [name:bytes]
        """
        entries = []
        # Raccogli tutti i nodi di tutti i peer (escluso il destinatario)
        for pid, peer_nodes in self._nodes.items():
            if pid == to_peer_id:
                continue
            for tname, node in peer_nodes.items():
                obj_id = self._obj_to_id.get(id(node), 0)
                entries.append((tname, pid, obj_id))

        payload = struct.pack("<BH", MsgType.PEER_LIST, len(entries))
        for tname, owner, obj_id in entries:
            name_bytes = tname.encode("utf-8")
            payload += struct.pack("<BII", len(name_bytes), owner, obj_id)
            payload += name_bytes

        if self._transport:
            self._transport.send(to_peer_id, payload, reliable=True)
            cprint.info(f"Net: sent PEER_LIST ({len(entries)} nodes) "
                        f"to peer={to_peer_id}")

    def _handle_peer_list(self, payload: bytes):
        """Client riceve la lista nodi dall'host e crea quelli mancanti.

        Formato v2: [count:u16] per nodo: [name_len:u8] [owner:u32] [obj_id:u32] [name:bytes]
        """
        if len(payload) < 2:
            return
        count = struct.unpack_from("<H", payload)[0]
        offset = 2
        for _ in range(count):
            if offset + 9 > len(payload):
                break
            name_len, owner, obj_id = struct.unpack_from("<BII", payload, offset)
            offset += 9
            if offset + name_len > len(payload):
                break
            tname = payload[offset:offset + name_len].decode("utf-8", errors="replace")
            offset += name_len

            # Crea il nodo se non esiste gia'
            peer_nodes = self._nodes.get(owner, {})
            if tname in peer_nodes:
                continue
            factory_info = self._node_factories.get(tname)
            if factory_info is None:
                cprint.warning(f"Net: PEER_LIST unknown type '{tname}'")
                continue
            factory, auto_spawn = factory_info
            node = factory(owner=owner)
            node._net_type_name = tname
            self._nodes.setdefault(owner, {})[tname] = node
            # Popola auto_nodes cosi' Net.nodes include anche i peer indiretti
            if auto_spawn and owner not in self._auto_nodes:
                self._auto_nodes[owner] = node
            self._register_with_id(node, obj_id)
            cprint.info(f"Net: PEER_LIST created {tname} for peer={owner} "
                        f"obj_id={obj_id}")
            for cb in self._on_node_created:
                try:
                    cb(owner, node)
                except Exception as e:
                    cprint.warning(f"Net on_node_created error: {e}")

    def _register_with_id(self, obj: object, obj_id: int) -> int:
        """Registra un oggetto con un obj_id specifico (per nodi ricevuti dalla rete)."""
        self._registered[obj_id] = obj
        self._obj_to_id[id(obj)] = obj_id

        owner = getattr(obj, "_net_owner", self._local_id)
        if owner == self._local_id:
            self._local_objects.add(obj_id)
        else:
            self._remote_objects.add(obj_id)

        if not hasattr(obj, "_net_dirty"):
            obj._net_dirty = set()
        if not hasattr(obj, "_net_owner"):
            obj._net_owner = self._local_id

        # Registra RPC methods
        cls = type(obj)
        rpc_methods = self._rpc_class_cache.get(cls)
        if rpc_methods is None:
            rpc_methods = []
            for attr_name in dir(cls):
                attr = getattr(cls, attr_name, None)
                if attr and hasattr(attr, "_rpc_meta"):
                    rpc_methods.append((attr_name, attr._rpc_meta))
            self._rpc_class_cache[cls] = rpc_methods

        for attr_name, meta in rpc_methods:
            entry = (obj_id, attr_name, obj)
            self._rpc_dispatch.setdefault(meta.name_hash, []).append(entry)

        cprint.info(f"Net: register_with_id obj_id={obj_id} owner={owner} "
                    f"type={type(obj).__name__}")
        return obj_id

    def _send_spawn(self, type_name: str, owner: int, obj_id: int):
        """Invia SPAWN_NODE a tutti i peer."""
        name_bytes = type_name.encode("utf-8")
        payload = struct.pack("<BII", len(name_bytes), owner, obj_id) + name_bytes
        msg = struct.pack("<B", MsgType.SPAWN_NODE) + payload
        if self._transport:
            self._transport.send_all(msg, reliable=True)
            self._bytes_sent += len(msg)
            self._packets_sent += 1

    def _send_despawn(self, obj_id: int):
        """Invia DESPAWN_NODE a tutti i peer."""
        msg = struct.pack("<BI", MsgType.DESPAWN_NODE, obj_id)
        if self._transport:
            self._transport.send_all(msg, reliable=True)
            self._bytes_sent += len(msg)
            self._packets_sent += 1

    def _handle_spawn(self, peer_id: int, payload: bytes):
        """Gestisce un SPAWN_NODE ricevuto dalla rete."""
        if len(payload) < 9:
            return
        name_len, owner, obj_id = struct.unpack_from("<BII", payload)
        offset = 9
        if offset + name_len > len(payload):
            return
        tname = payload[offset:offset + name_len].decode("utf-8", errors="replace")

        factory_info = self._node_factories.get(tname)
        if factory_info is None:
            cprint.warning(f"Net: SPAWN unknown type '{tname}'")
            return
        factory, auto_spawn = factory_info
        node = factory(owner=owner)
        node._net_type_name = tname
        self._nodes.setdefault(owner, {})[tname] = node
        if auto_spawn and owner not in self._auto_nodes:
            self._auto_nodes[owner] = node
        self._register_with_id(node, obj_id)
        cprint.info(f"Net: spawned {tname} for peer={owner} obj_id={obj_id}")
        for cb in self._on_node_created:
            try:
                cb(owner, node)
            except Exception as e:
                cprint.warning(f"Net on_node_created error: {e}")

    def _handle_despawn(self, peer_id: int, payload: bytes):
        """Gestisce un DESPAWN_NODE ricevuto dalla rete."""
        if len(payload) < 4:
            return
        obj_id = struct.unpack_from("<I", payload)[0]
        obj = self._registered.get(obj_id)
        if obj is None:
            return
        owner = getattr(obj, "_net_owner", -1)
        tname = getattr(obj, "_net_type_name", "")
        self.unregister(obj)
        peer_nodes = self._nodes.get(owner)
        if peer_nodes and tname in peer_nodes:
            del peer_nodes[tname]
            if not peer_nodes:
                del self._nodes[owner]
        cprint.info(f"Net: despawned {tname} obj_id={obj_id}")
        for cb in self._on_node_removed:
            try:
                cb(owner, obj)
            except Exception as e:
                cprint.warning(f"Net on_node_removed error: {e}")

    def _compress_msg(self, msg_type: int, payload: bytes) -> bytes:
        """Costruisce un messaggio, comprimendolo se conviene."""
        if len(payload) > COMPRESSION_THRESHOLD:
            compressed = zlib.compress(payload, level=1)
            if len(compressed) < len(payload):
                return struct.pack("<B", msg_type | COMPRESSION_FLAG) + compressed
        return struct.pack("<B", msg_type) + payload

    def _send_rpc_packet(self, rpc_data: bytes, target: str,
                         peer_id: int | None, reliable: bool):
        """Invia un pacchetto RPC.

        In topologia star, i client inviano sempre all'host (peer 0).
        Il target_peer nel payload dice all'host a chi inoltrare.
        """
        if self._transport is None:
            return

        msg = self._compress_msg(MsgType.RPC_CALL, rpc_data)
        self._bytes_sent += len(msg)
        self._packets_sent += 1

        if target == "all":
            self._transport.send_all(msg, reliable)
        elif target == "host":
            if not self._is_host:
                self._transport.send(0, msg, reliable)
        elif target == "others":
            self._transport.send_all(msg, reliable, exclude=self._local_id)
        elif target == "peer" and peer_id is not None:
            if self._is_host:
                # Host: invia diretto al peer
                self._transport.send(peer_id, msg, reliable)
            else:
                # Client: invia all'host, che fa relay al target
                self._transport.send(0, msg, reliable)
