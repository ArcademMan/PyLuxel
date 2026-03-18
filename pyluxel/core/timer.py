"""pyluxel.core.timer -- Timer e countdown utility.

Uso:

    timer = Timer(90.0, on_complete=self.end_round)
    timer.update(dt)
    print(timer.formatted())  # "01:30"
    print(timer.remaining)    # 87.3
"""

from __future__ import annotations

__all__ = ["Timer"]


class Timer:
    """Countdown timer con callback e formattazione.

    Args:
        duration: durata in secondi
        on_complete: callback opzionale chiamato quando il timer scade
        auto_start: se True, il timer parte subito (default True)
    """

    __slots__ = ('_duration', '_remaining', '_running', '_finished',
                 '_on_complete')

    def __init__(self, duration: float, on_complete=None,
                 auto_start: bool = True):
        self._duration = max(0.0, duration)
        self._remaining = self._duration
        self._running = auto_start
        self._finished = False
        self._on_complete = on_complete

    @property
    def remaining(self) -> float:
        """Secondi rimanenti."""
        return self._remaining

    @property
    def elapsed(self) -> float:
        """Secondi trascorsi."""
        return self._duration - self._remaining

    @property
    def duration(self) -> float:
        """Durata totale."""
        return self._duration

    @property
    def progress(self) -> float:
        """Progresso da 0.0 (inizio) a 1.0 (fine)."""
        if self._duration <= 0:
            return 1.0
        return 1.0 - self._remaining / self._duration

    @property
    def running(self) -> bool:
        """True se il timer sta contando."""
        return self._running

    @property
    def finished(self) -> bool:
        """True se il timer ha raggiunto 0."""
        return self._finished

    def update(self, dt: float):
        """Avanza il timer. Chiama on_complete quando scade."""
        if not self._running or self._finished:
            return
        self._remaining -= dt
        if self._remaining <= 0:
            self._remaining = 0.0
            self._finished = True
            self._running = False
            if self._on_complete:
                self._on_complete()

    def start(self):
        """Avvia o riprende il timer."""
        if not self._finished:
            self._running = True

    def pause(self):
        """Mette in pausa il timer."""
        self._running = False

    def reset(self, duration: float | None = None):
        """Resetta il timer. Se duration e' specificata, cambia la durata."""
        if duration is not None:
            self._duration = max(0.0, duration)
        self._remaining = self._duration
        self._finished = False
        self._running = True

    def formatted(self, show_ms: bool = False) -> str:
        """Formatta il tempo rimanente come MM:SS o MM:SS.mm.

        Args:
            show_ms: se True, aggiunge i centesimi (MM:SS.CC)
        """
        t = max(0.0, self._remaining)
        mins = int(t) // 60
        secs = int(t) % 60
        if show_ms:
            cs = int((t - int(t)) * 100)
            return f"{mins:02d}:{secs:02d}.{cs:02d}"
        return f"{mins:02d}:{secs:02d}"
