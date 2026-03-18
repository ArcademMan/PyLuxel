"""pyluxel.animation.state_machine -- State machine per animazioni."""

from __future__ import annotations

from pyluxel.animation.animator import Animation, Animator


class _StateEntry:
    """Singolo stato registrato nella state machine."""
    __slots__ = ("animation", "lock", "blend_out")

    def __init__(self, animation: Animation, lock: bool, blend_out: float):
        self.animation = animation
        self.lock = lock
        self.blend_out = blend_out


class AnimStateMachine:
    """State machine per gestire transizioni animate con crossfade.

    Registra stati con ``add()``, poi cambia stato con ``set()``.
    Gli stati con ``lock=True`` (es. attacco, salto) non possono essere
    interrotti: al completamento tornano automaticamente allo stato
    ``default``.

    Esempio::

        sm = AnimStateMachine(animator)
        sm.add("idle", IDLE)
        sm.add("walk", WALK)
        sm.add("attack", ATTACK, lock=True)
        sm.default = "idle"
        sm.set("idle")

        # nel game loop
        sm.set("walk", blend=0.15)   # transizione smooth
        sm.set("attack", blend=0.1)  # lock fino a completamento
    """

    def __init__(self, animator: Animator):
        self._animator = animator
        self._states: dict[str, _StateEntry] = {}
        self._current: str = ""
        self._locked: bool = False
        self.default: str = ""

    # ------------------------------------------------------------------ API

    def add(self, name: str, animation: Animation, *,
            lock: bool = False, blend_out: float = 0.15) -> None:
        """Registra uno stato.

        Parameters
        ----------
        name : str
            Nome univoco dello stato (es. "idle", "walk").
        animation : Animation
            Animazione da riprodurre in questo stato.
        lock : bool
            Se True, lo stato non puo' essere interrotto. Al completamento
            torna automaticamente a ``self.default`` con ``blend_out``.
        blend_out : float
            Durata del crossfade quando si esce da uno stato locked
            verso il default.
        """
        self._states[name] = _StateEntry(animation, lock, blend_out)

    def has_state(self, name: str) -> bool:
        """True se lo stato e' registrato."""
        return name in self._states

    def get_states(self) -> list[str]:
        """Ritorna la lista dei nomi degli stati registrati."""
        return list(self._states.keys())

    def reset_to_default(self) -> bool:
        """Forza transizione allo stato default."""
        if not self.default:
            return False
        self._locked = False
        self._current = ""
        return self.set(self.default)

    def set(self, name: str, *, blend: float = 0.0) -> bool:
        """Transizione verso uno stato.

        Returns
        -------
        bool
            True se la transizione e' avvenuta, False se bloccata da un lock
            o lo stato non esiste o e' gia' corrente.
        """
        if self._locked or name == self._current:
            return False

        entry = self._states.get(name)
        if entry is None:
            return False

        self._current = name

        if entry.lock:
            self._locked = True
            self._animator.play(
                entry.animation, blend_time=blend,
                on_complete=self._on_lock_done,
            )
        else:
            self._animator.play(entry.animation, blend_time=blend)

        return True

    def force(self, name: str, *, blend: float = 0.0) -> bool:
        """Transizione forzata, ignora il lock (es. morte del personaggio)."""
        self._locked = False
        self._current = ""
        return self.set(name, blend=blend)

    # ------------------------------------------------------------------ props

    @property
    def state(self) -> str:
        """Nome dello stato corrente."""
        return self._current

    @property
    def locked(self) -> bool:
        """True se lo stato corrente non puo' essere interrotto."""
        return self._locked

    # ------------------------------------------------------------------ internal

    def _on_lock_done(self) -> None:
        """Callback: animazione locked completata, torna al default."""
        self._locked = False
        self._current = ""
        if self.default and self.default in self._states:
            entry = self._states[self.default]
            self.set(self.default, blend=entry.blend_out)
