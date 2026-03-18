# EventBus

Lightweight pub/sub event dispatcher. Global singleton `Events` follows the same pattern as `Input`, `Sound`, `Net`.

## Quick Start

```python
from pyluxel import Events

# Subscribe
def on_player_died(**kwargs):
    print(f"Player died: {kwargs}")

Events.on("player_died", on_player_died)

# Emit
Events.emit("player_died", player=p, cause="lava")

# Unsubscribe
Events.off("player_died", on_player_died)
```

## API

### `Events.on(event, listener, *, priority=0) -> listener`

Register a listener for an event. Lower priority values run first (default `0`). Returns the listener for use as a decorator. Duplicate subscriptions of the same listener are ignored.

```python
# As decorator
@Events.on("enemy_killed")
def handle_kill(**kwargs):
    drop_loot(kwargs["enemy"])

# With priority (runs before default-priority listeners)
Events.on("enemy_killed", play_sfx, priority=-10)
```

### `Events.once(event, listener, *, priority=0) -> listener`

Like `on()`, but auto-removes the listener after the first call.

```python
Events.once("map_loaded", lambda **kw: print("First load!"))
```

### `Events.off(event, listener)`

Remove a listener. No-op if not found. Works for both `on()` and `once()` listeners.

### `Events.emit(event, **kwargs)`

Fire an event, calling all listeners in priority order with the given keyword arguments. Safe to call `on`/`off`/`once` inside a listener.

### `Events.clear(event=None)`

Remove all listeners for a specific event, or all listeners if `event` is `None`.

### `Events.has(event) -> bool`

Returns `True` if at least one listener is registered for the event.

### `Events.count(event) -> int`

Returns number of listeners for the event.

## Multiple Instances

The `Events` singleton covers most use cases. For isolated buses (e.g., per-scene):

```python
from pyluxel import EventBus

local_bus = EventBus()
local_bus.on("door_opened", handler)
```

## Performance Notes

- Listener lookup is **O(1)** per event name (dict).
- Emit is **O(n)** where n = listeners for that event.
- A snapshot is taken before iteration, so mutations during emit are safe.
- Priority ordering uses `bisect.insort_right` — O(log n) on subscribe.
- No allocations in the emit path beyond the list slice copy.
