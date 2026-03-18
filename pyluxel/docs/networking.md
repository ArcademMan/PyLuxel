# Networking

P2P multiplayer networking with host/client model. Supports **UDP** (dev/LAN) and **Steam Networking Sockets** (production, relay-based, zero port forwarding). Uses App ID 480 (Spacewar) for free dev testing.

---

## Quick Start

### Host a Game

```python
from pyluxel import App, Net, Input
import pygame

class HostGame(App):
    def setup(self):
        Input.bind("quit", pygame.K_ESCAPE)

        Net.on_connect(lambda pid: print(f"Player {pid} joined!"))
        Net.on_disconnect(lambda pid: print(f"Player {pid} left"))
        Net.host(transport="udp")      # or "steam" for Steam relay
        self._net_active = True

    def update(self, dt):
        if Input.pressed("quit"):
            self.quit()

    def draw_overlay(self):
        self.draw_text(f"Hosting | Players: {Net.peer_count}", 10, 10, size=20)

HostGame(1280, 720, "Host").run()
```

### Join a Game

```python
from pyluxel import App, Net

class ClientGame(App):
    def setup(self):
        Net.on_connect(lambda pid: print("Connected to host!"))
        Net.join("127.0.0.1", transport="udp")
        self._net_active = True

ClientGame(1280, 720, "Client").run()
```

---

## Init (optional)

```python
Net.init(transport="steam", app_id=480)
```

Initializes the transport without connecting. Useful to have `Net.local_name` (Steam player name) available before calling `host()` or `join()` -- for example, to display the player's name in the lobby UI. If not called, `host()` / `join()` create the transport automatically.

---

## Transport

Two transports available. The API is identical -- just change the `transport` parameter.

### UDP (dev/LAN)

```python
Net.host(port=7777, transport="udp")
Net.join("192.168.1.100", port=7777, transport="udp")
```

- Direct socket connection
- Works on localhost and LAN without any setup
- Includes reliability layer (sequence numbers, ack, resend)
- No NAT traversal -- for internet play, port forwarding required

### Steam (production)

```python
Net.host(transport="steam", app_id=480)
Net.join("76561198012345678", transport="steam", app_id=480)
```

- Uses Valve's relay network -- zero port forwarding
- Uses the bundled `steam_api64.dll` via ctypes (no external dependencies)
- App ID 480 (Spacewar) works for free during development
- If `steam_api64.dll` is not found, falls back to UDP with a warning
- For `join()`, the address is the host's Steam ID as a string

---

## Callbacks

Register callbacks to react to network events.

```python
Net.on_connect(fn)       # fn(peer_id: int)  -- new peer connected
Net.on_disconnect(fn)    # fn(peer_id: int)  -- peer disconnected
```

Multiple callbacks can be registered for the same event.

---

## Network Events

Lightweight event bus for one-shot networked events (explosions, pickups, sound effects). No registered object required -- simpler than RPC for fire-and-forget events.

### Register a handler

```python
@Net.on_event("explosion")
def on_explosion(peer_id, x, y, radius):
    spawn_particles(x, y, radius)
    play_sound("boom", x, y)
```

The handler receives `peer_id` (who emitted the event) followed by the event arguments.

### Emit events

```python
# Broadcast to all peers (including self)
Net.emit("explosion", x, y, radius)
Net.emit("footstep", x, y, reliable=False)    # unreliable for non-critical

# To a specific peer
Net.emit_to(peer_id, "private_msg", "hello")

# To host only (peer 0)
Net.emit_to_host("buy_item", item_id)

# To a specific client (rejects peer_id=0)
Net.emit_to_client(peer_id, "loot_drop", item_id, x, y)
```

| Method | Target | Executes locally |
|--------|--------|------------------|
| `emit(name, *args)` | All peers | Yes |
| `emit_to(pid, name, *args)` | Specific peer | Only if pid == self |
| `emit_to_host(name, *args)` | Host (peer 0) | Only if we are host |
| `emit_to_client(pid, name, *args)` | Specific client | Only if pid == self |

All methods accept `reliable=True` (default) or `reliable=False`.

In star topology (clients only connect to host), targeted events from a client are routed through the host automatically.

### Supported argument types

`int`, `float`, `bool`, `str`, `tuple[float, float]` (vec2), `bytes`

---

## State Synchronization

The `synced()` descriptor automatically synchronizes variables across the network. Only the owner of an object can write to synced fields.

```python
from pyluxel import synced

class Player:
    x = synced(0.0, interpolate=True, lerp_speed=15.0)
    y = synced(0.0, interpolate=True, lerp_speed=15.0)
    health = synced(100, reliable=True)
    name = synced("", reliable=True)

    def __init__(self, owner: int):
        self._net_owner = owner    # peer_id that controls this object
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `default` | any | `None` | Initial value |
| `reliable` | `bool` | `False` | Send changes on reliable channel (guaranteed delivery) |
| `interpolate` | `bool` | `False` | Smooth remote values instead of snapping |
| `lerp_speed` | `float` | `10.0` | Interpolation speed (fallback when timestamps unavailable) |

### Reliable vs unreliable fields

Fields marked `reliable=True` (e.g. health, score, name) are sent on a reliable channel -- guaranteed delivery, no packet loss. Fields with `reliable=False` (default, e.g. position) are sent unreliable for lower latency. The engine automatically splits dirty fields into separate packets by reliability.

### Supported types

`int`, `float`, `bool`, `str`, `tuple[float, float]` (vec2), `bytes`

### How it works

1. Define a `NetNode` subclass with `synced()` fields
2. Register it with `Net.register_node_type()` (auto-spawn) or use `Net.spawn()` (manual)
3. The engine handles registration, sync, and cleanup automatically
4. The owner modifies fields normally -- they're automatically marked dirty
5. At 20 Hz (configurable via `Net.sync_tick_rate = 30`), dirty fields are sent to all peers
6. Remote peers receive the value and either snap or interpolate to it
7. Out-of-order packets are automatically dropped (per-object sequence check)

### Timestamped interpolation

Sync packets include a timestamp from the network clock. When timestamps are available, interpolation uses time-based lerp between the last two snapshots instead of blind exponential lerp. This produces smoother results on unstable connections. Falls back to `lerp_speed` if timestamps are unavailable.

### Object limit

Each owner (peer) can register up to 1000 objects by default. Configure before connecting:

```python
Net.obj_per_owner = 5000   # must be the same on all peers
```

---

## Remote Procedure Calls (RPC)

The `@rpc` decorator marks a method as callable across the network.

```python
from pyluxel import rpc, RPCTarget

class Player:
    @rpc(target="all", reliable=True)
    def take_damage(self, amount: int):
        self.health -= amount

    @rpc(target="host")
    def request_respawn(self):
        # Only the host processes this
        self.health = 100
        self.x, self.y = 640, 360

    @rpc(target="others")
    def chat(self, message: str):
        print(f"{self.name}: {message}")
```

When called locally, the method:
1. Executes locally
2. Serializes the call and sends it to the appropriate peers

| Target | Description |
|--------|-------------|
| `RPCTarget.ALL` / `"all"` | Everyone receives (including sender) |
| `RPCTarget.HOST` / `"host"` | Only the host receives |
| `RPCTarget.OTHERS` / `"others"` | Everyone except the sender |
| `RPCTarget.PEER` / `"peer"` | A specific peer (via `_rpc_peer_id`) |

### Sending to a specific peer

Override the decorator target by passing `_rpc_peer_id`:

```python
player.take_damage(10, _rpc_peer_id=3)   # only peer 3 receives
player.take_damage(10)                     # uses the decorator target
```

In star topology, client-to-client RPCs are routed through the host automatically.

### Host-only decorator

```python
from pyluxel import host_only

class GameManager:
    @host_only
    def spawn_enemy(self, x, y):
        # Only runs if Net.is_host is True
        ...
```

### RPC rate limiting

The host limits RPC relay to prevent flooding:

```python
Net.rpc_rate_limit = 300   # max RPC relay per peer per second (default 300, 0 = no limit)
```

### Supported argument types

`int`, `float`, `bool`, `str`, `tuple[float, float]` (vec2), `bytes`

---

## Network Clock

Synchronized clock between host and clients. The host sends its timestamp every 2 seconds, clients compute the offset using RTT/2 with median filtering (8 samples, resistant to latency spikes).

```python
Net.net_time -> float       # synchronized network time (seconds)
Net.clock_offset -> float   # offset between local and host clock
Net.clock_synced -> bool    # True after first sync
```

On the host, `net_time` equals `time.perf_counter()`. On clients, it's aligned to the host's clock. Used internally for timestamped interpolation, but available for game logic (e.g. synchronized timers, cooldowns).

---

## Lobby System

Lobby/room management. With UDP uses shareable codes. With Steam uses native lobbies with friend invites and "Join Game" from the friends list.

### UDP Lobbies (codes)

```python
# Host creates a lobby
Net.lobby.create("My Room", max_players=4)
print(f"Share this code: {Net.lobby.code}")   # e.g. "2334CP2EE9"

# Friend joins with the code
Net.lobby.join_code("2334CP2EE9")
```

### Steam Lobbies (friend invites + Join Game)

```python
# Host creates a Steam lobby (visible to friends by default)
Net.lobby.create("My Room", max_players=4)
# Friends can now see "Join Game" on the host's Steam profile!

# Or make it public (visible to everyone)
Net.lobby.create("My Room", max_players=4, public=True)

# Invite a specific friend
friends = Net.lobby.get_friends()   # list of online friends
for f in friends:
    print(f"{f['name']} (ID: {f['steam_id']}, online: {f['online']})")

Net.lobby.invite(friends[0]["steam_id"])   # sends Steam overlay notification

# See who's in the lobby
members = Net.lobby.get_members()
for m in members:
    print(f"{m['name']} {'(Host)' if m['is_host'] else ''}")

# Set lobby metadata (visible to all members)
Net.lobby.set_data("map", "arena")
Net.lobby.set_data("mode", "deathmatch")
map_name = Net.lobby.get_data("map")

# Leave
Net.lobby.leave()
```

When a friend clicks **"Join Game"** on the host's Steam profile or accepts an invite, Steam automatically connects them to the lobby -- no codes, no IP addresses, no port forwarding.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `lobby.code` | `str \| None` | Room code (UDP) or lobby ID (Steam) |
| `lobby.name` | `str` | Lobby name |
| `lobby.max_players` | `int` | Max allowed players |
| `lobby.player_count` | `int` | Current player count |
| `lobby.is_in_lobby` | `bool` | True if in a lobby |
| `lobby.is_full` | `bool` | True if lobby is full |
| `lobby.is_steam` | `bool` | True if using Steam lobbies |

### Methods

| Method | Description |
|--------|-------------|
| `lobby.create(name, max_players, public, on_created)` | Create a lobby |
| `lobby.join_code(code, on_joined)` | Join by code/ID |
| `lobby.invite(steam_id)` | Invite a friend (Steam only) |
| `lobby.leave()` | Leave the lobby |
| `lobby.get_friends()` | Get online friends list (Steam only) |
| `lobby.get_members()` | Get lobby members (Steam only) |
| `lobby.set_data(key, value)` | Set lobby metadata (Steam only) |
| `lobby.get_data(key)` | Get lobby metadata (Steam only) |

---

## Node Factory

Automatically create synchronized objects for each peer. Two forms available:

### Simple (auto-spawn)

One node type per peer, created automatically on connect:

```python
Net.register_node_type(NetPlayer)   # auto_spawn=True, name="NetPlayer"
```

Nodes are created for every peer (including self) on connect, and removed on disconnect.

`Net.nodes` is a **live dict** (`{peer_id: node}`) auto-maintained by the engine -- entries are added on connect and removed on disconnect. You can use it directly as your player dict without writing `on_node_created`/`on_node_removed` callbacks:

```python
self.players = Net.nodes   # alias -- same dict, auto-updated
```

```python
Net.on_node_created(fn)    # fn(peer_id, node) -- optional, for game-specific logic
Net.on_node_removed(fn)    # fn(peer_id, node) -- optional, for game-specific logic
Net.get_node(peer_id)      # returns the auto_spawn node
Net.nodes                  # {peer_id: node} live dict, auto-maintained
```

### Multi-type

Register multiple node types. Use `spawn()`/`despawn()` for on-demand creation:

```python
Net.register_node_type("Bullet", BulletNode)
Net.register_node_type("PowerUp", PowerUpNode, auto_spawn=True)

# Spawn a bullet (replicated to all peers)
bullet = Net.spawn("Bullet", speed=500)

# Despawn it (replicated to all peers)
Net.despawn(bullet)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `auto_spawn` | `bool` | If True, one instance is created per peer on connect (default False) |

### NetNode base class

All node types should inherit from `NetNode`:

```python
from pyluxel import NetNode, synced, rpc

class BulletNode(NetNode):
    x = synced(0.0, interpolate=True)
    y = synced(0.0, interpolate=True)

    def __init__(self, owner: int, speed: float = 300):
        super().__init__(owner)
        self.speed = speed

    @rpc(target="all")
    def explode(self):
        # ...
```

---

## Protocol Versioning

The protocol includes automatic version checking during handshake. Both UDP and Steam transports validate that host and client run the same protocol version. Connections with mismatched versions are rejected silently.

The current protocol version is `5` (stored in `pyluxel.net.protocol.PROTOCOL_VERSION`).

---

## Compression

Payloads larger than 128 bytes are automatically compressed with zlib (level 1, fast). Compression is transparent -- the receiver decompresses automatically. If the compressed payload is not smaller than the original, it is sent uncompressed.

Applies to: STATE_SYNC, RPC_CALL, NET_EVENT.

---

## Bandwidth Stats

```python
stats = Net.stats
# {
#     "sent_bps": 1200,    # bytes sent per second
#     "recv_bps": 800,     # bytes received per second
#     "sent_pps": 25,      # packets sent per second
#     "recv_pps": 20,      # packets received per second
#     "peers": 3,          # connected peer count
# }
```

Stats are updated once per second during `Net.poll()`.

---

## Properties

```python
Net.is_host -> bool          # True if hosting
Net.is_connected -> bool     # True if connected
Net.local_id -> int          # Our peer ID (host = 0)
Net.local_name -> str        # Steam player name (empty if not Steam)
Net.peer_count -> int        # Number of connected peers
Net.peers -> list[int]       # List of peer IDs
Net.get_peer(pid) -> Peer    # Get peer info
Net.get_player_name(pid) -> str  # Get peer's Steam name
Net.sync_tick_rate = 20      # Sync frequency in Hz (default 20)
Net.obj_per_owner = 1000     # Max objects per owner (set before host/join)
Net.rpc_rate_limit = 300     # Max RPC relay per peer/second (0 = no limit)
Net.net_time -> float        # Synchronized network time
Net.clock_offset -> float    # Clock offset from host (seconds)
Net.clock_synced -> bool     # True after first clock sync
Net.stats -> dict            # Bandwidth stats (see above)
Net.context                  # Application context (accessible from RPCs)
```

### Peer

```python
peer = Net.get_peer(peer_id)
peer.id -> int               # Peer ID
peer.name -> str             # Player name (Steam)
peer.steam_id -> int         # Steam ID (0 if not Steam)
peer.rtt -> float            # Round-trip time in seconds
peer.state -> str            # "connecting" | "connected" | "disconnected"
peer.is_connected -> bool
peer.uptime -> float         # Seconds since connection
```

---

## App Integration

When using the `App` class, set `self._net_active = True` to enable automatic polling and cleanup:

```python
class MyGame(App):
    def setup(self):
        Net.host(transport="udp")
        self._net_active = True   # enables Net.poll() in game loop
```

Without `App`, call `Net.poll(dt)` manually every frame:

```python
while running:
    dt = clock.tick(60) / 1000.0
    Net.poll(dt)
    # ... game logic ...
```

---

## Complete Example

```python
from pyluxel import App, Net, NetNode, Input, rpc, synced
import pygame

class NetPlayer(NetNode):
    x = synced(0.0, interpolate=True, lerp_speed=15.0)
    y = synced(0.0, interpolate=True, lerp_speed=15.0)
    name = synced("", reliable=True)

    def __init__(self, owner: int):
        super().__init__(owner)

    @rpc(target="all")
    def chat(self, message: str):
        print(f"[{self.name}]: {message}")

class MyGame(App):
    def setup(self):
        Input.bind("right", pygame.K_d)
        Input.bind("left", pygame.K_a)
        Input.bind("up", pygame.K_w)
        Input.bind("down", pygame.K_s)

        Net.register_node_type(NetPlayer)    # auto_spawn=True
        self.players = Net.nodes             # live dict {peer_id: node}

        Net.host(transport="udp")
        self._net_active = True

    def update(self, dt):
        me = self.players.get(Net.local_id)
        if me:
            speed = 200 * dt
            if Input.held("right"): me.x += speed
            if Input.held("left"):  me.x -= speed
            if Input.held("down"):  me.y += speed
            if Input.held("up"):    me.y -= speed

    def draw(self):
        for pid, p in self.players.items():
            is_me = pid == Net.local_id
            self.draw_rect(p.x - 16, p.y - 16, 32, 32,
                           r=0, g=1 if is_me else 0, b=0 if is_me else 1)

    def draw_overlay(self):
        self.draw_text(f"Players: {len(self.players)} | "
                       f"{'Host' if Net.is_host else 'Client'}", 10, 10, size=18)

MyGame(1280, 720, "Multiplayer Demo").run()
```
