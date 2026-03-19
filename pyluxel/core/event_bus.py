"""pyluxel.core.event_bus -- Lightweight, high-performance event bus.

Usage::

    from pyluxel import Events

    # Subscribe
    Events.on("player_died", my_handler)
    Events.once("player_died", one_shot_handler)   # auto-removes after first call

    # Emit
    Events.emit("player_died", player=p, cause="lava")

    # Unsubscribe
    Events.off("player_died", my_handler)

    # Clear all listeners for an event (useful on scene exit)
    Events.clear("player_died")

    # Clear everything
    Events.clear()

Listeners are called in priority order (lower = earlier, default 0).
Listeners can safely call ``on`` / ``off`` / ``once`` during ``emit``.
"""

from __future__ import annotations

from bisect import insort_right
from collections import defaultdict
from typing import Any, Callable

__all__ = ["EventBus", "Events"]

# Sentinel for _OnceWrapper identity checks
_SENTINEL = object()


class _Entry:
    """A (priority, listener) pair, ordered by priority then insertion order."""

    __slots__ = ("priority", "listener", "_seq")

    _counter: int = 0

    def __init__(self, priority: int, listener: Callable) -> None:
        self.priority = priority
        self.listener = listener
        _Entry._counter += 1
        self._seq = _Entry._counter

    def __lt__(self, other: _Entry) -> bool:  # type: ignore[override]
        if self.priority != other.priority:
            return self.priority < other.priority
        return self._seq < other._seq


class _OnceWrapper:
    """Wraps a listener so it auto-removes after first invocation."""

    __slots__ = ("fn", "event", "bus")

    def __init__(self, fn: Callable, event: str, bus: EventBus) -> None:
        self.fn = fn
        self.event = event
        self.bus = bus

    def __call__(self, **kwargs: Any) -> Any:
        self.bus.off(self.event, self)
        return self.fn(**kwargs)


class EventBus:
    """Central pub/sub event dispatcher.

    * **O(1)** listener lookup per event name (dict + list).
    * **O(n)** emit where *n* is the number of listeners for that event.
    * Listeners receive only **keyword arguments** from ``emit``.
    * Safe to ``on``/``off``/``once`` inside a listener callback.
    """

    __slots__ = ("_listeners",)

    def __init__(self) -> None:
        self._listeners: defaultdict[str, list[_Entry]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Subscribe
    # ------------------------------------------------------------------

    def on(self, event: str, listener: Callable, *, priority: int = 0) -> Callable:
        """Register *listener* for *event*.

        Parameters
        ----------
        event:
            Event name (any string).
        listener:
            Callable that accepts ``**kwargs``.
        priority:
            Lower values run first.  Default ``0``.

        Returns the listener (handy as a decorator).
        """
        entries = self._listeners[event]
        # Prevent double-subscribe of the same listener
        # Uses == instead of `is` because bound methods create new objects
        # on each attribute access (self.method is self.method → False)
        for e in entries:
            if e.listener == listener:
                return listener
        insort_right(entries, _Entry(priority, listener))
        return listener

    def once(self, event: str, listener: Callable, *, priority: int = 0) -> Callable:
        """Like :meth:`on`, but auto-removes after the first call."""
        wrapper = _OnceWrapper(listener, event, self)
        self.on(event, wrapper, priority=priority)
        return listener

    # ------------------------------------------------------------------
    # Unsubscribe
    # ------------------------------------------------------------------

    def off(self, event: str, listener: Callable) -> None:
        """Remove *listener* from *event*.  No-op if not found."""
        entries = self._listeners.get(event)
        if entries is None:
            return
        for i, e in enumerate(entries):
            lsn = e.listener
            if lsn == listener or (isinstance(lsn, _OnceWrapper) and lsn.fn == listener):
                entries.pop(i)
                break
        if not entries:
            del self._listeners[event]

    def clear(self, event: str | None = None) -> None:
        """Remove listeners.  If *event* is ``None``, remove **all**."""
        if event is None:
            self._listeners.clear()
        else:
            self._listeners.pop(event, None)

    # ------------------------------------------------------------------
    # Emit
    # ------------------------------------------------------------------

    def emit(self, event: str, **kwargs: Any) -> None:
        """Fire *event*, calling each listener with *kwargs*.

        A snapshot of the listener list is iterated so that listeners may
        safely subscribe or unsubscribe during the call.
        """
        entries = self._listeners.get(event)
        if entries is None:
            return
        # Snapshot: copy the list so mutations during iteration are safe.
        for entry in entries[:]:
            entry.listener(**kwargs)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def has(self, event: str) -> bool:
        """Return ``True`` if *event* has at least one listener."""
        return bool(self._listeners.get(event))

    def count(self, event: str) -> int:
        """Return number of listeners for *event*."""
        entries = self._listeners.get(event)
        return len(entries) if entries else 0


# Global singleton -- mirrors the Input / Sound / Net pattern.
Events = EventBus()
