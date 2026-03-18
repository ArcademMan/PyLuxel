"""pyluxel.animation.animator -- Pose, Animation, Animator per keyframe interpolation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto


class LoopMode(Enum):
    """Modalita' di ripetizione di un'animazione."""
    ONCE = auto()
    LOOP = auto()
    PING_PONG = auto()


class Pose:
    """Insieme di angoli (gradi) per nome osso + offset root opzionale.

    Usato come keyframe nelle animazioni. Solo le ossa presenti nel dict
    vengono animate; le altre mantengono il loro angolo corrente.

    L'offset (x, y) e' puramente visivo: sposta lo skeleton durante
    l'animazione senza modificare le coordinate logiche del personaggio.
    """

    __slots__ = ("angles", "offset_x", "offset_y")

    def __init__(self, angles: dict[str, float] | None = None,
                 offset_x: float = 0.0, offset_y: float = 0.0):
        self.angles: dict[str, float] = dict(angles) if angles else {}
        self.offset_x = offset_x
        self.offset_y = offset_y

    def __repr__(self) -> str:
        if self.offset_x or self.offset_y:
            return f"Pose({self.angles}, offset=({self.offset_x}, {self.offset_y}))"
        return f"Pose({self.angles})"

    def clone(self) -> Pose:
        """Crea una copia della posa."""
        return Pose(dict(self.angles), self.offset_x, self.offset_y)

    def set_angle(self, name: str, angle: float) -> None:
        """Imposta l'angolo di un osso specifico."""
        self.angles[name] = angle

    def get_angle(self, name: str) -> float | None:
        """Ritorna l'angolo di un osso, o None se non presente."""
        return self.angles.get(name)

    @staticmethod
    def lerp(a: Pose, b: Pose, t: float) -> Pose:
        """Interpola due pose con shortest-path per gli angoli."""
        out = Pose()
        Pose.lerp_into(a, b, t, out)
        return out

    @staticmethod
    def lerp_into(a: Pose, b: Pose, t: float, out: Pose) -> None:
        """Interpola a -> b scrivendo in out. Zero allocazioni."""
        result = out.angles
        result.clear()
        a_angles = a.angles
        b_angles = b.angles
        # Chiavi presenti in a
        for key, va in a_angles.items():
            vb = b_angles.get(key, 0.0)
            diff = (vb - va) % 360.0
            if diff > 180.0:
                diff -= 360.0
            result[key] = va + diff * t
        # Chiavi solo in b (va = 0)
        for key, vb in b_angles.items():
            if key not in a_angles:
                diff = vb % 360.0
                if diff > 180.0:
                    diff -= 360.0
                result[key] = diff * t
        # Interpola offset root
        out.offset_x = a.offset_x + (b.offset_x - a.offset_x) * t
        out.offset_y = a.offset_y + (b.offset_y - a.offset_y) * t


@dataclass(frozen=True)
class Animation:
    """Sequenza di keyframe (tempo normalizzato 0-1, Pose) con durata esplicita.

    I tempi dei keyframe sono normalizzati tra 0.0 e 1.0.
    La durata reale in secondi e' definita dal campo ``duration``.
    """
    name: str
    keyframes: tuple[tuple[float, Pose], ...]
    loop_mode: LoopMode = LoopMode.LOOP
    duration: float = 1.0

    def _wrap_time(self, t: float) -> float:
        """Clamp / wrap del tempo in base al loop mode."""
        dur = self.duration
        if dur <= 0:
            return 0.0
        if self.loop_mode == LoopMode.ONCE:
            return max(0.0, min(dur, t))
        if self.loop_mode == LoopMode.LOOP:
            return t % dur
        # PING_PONG
        cycle = t % (dur * 2)
        return dur * 2 - cycle if cycle > dur else cycle

    def sample(self, t: float) -> Pose:
        """Campiona la posa al tempo t (secondi). Alloca una nuova Pose."""
        out = Pose()
        self.sample_into(t, out)
        return out

    def sample_into(self, t: float, out: Pose) -> None:
        """Campiona la posa al tempo t scrivendo in out. Zero allocazioni."""
        if not self.keyframes:
            out.angles.clear()
            out.offset_x = 0.0
            out.offset_y = 0.0
            return
        if len(self.keyframes) == 1:
            d = out.angles
            d.clear()
            p = self.keyframes[0][1]
            d.update(p.angles)
            out.offset_x = p.offset_x
            out.offset_y = p.offset_y
            return

        t = self._wrap_time(t)
        # Converti tempo reale in normalizzato 0-1
        norm = t / self.duration if self.duration > 0 else 0.0

        # Trova i due keyframe tra cui interpolare
        for i in range(len(self.keyframes) - 1):
            t0, p0 = self.keyframes[i]
            t1, p1 = self.keyframes[i + 1]
            if t0 <= norm <= t1:
                seg = t1 - t0
                if seg <= 0:
                    out.angles.clear()
                    out.angles.update(p0.angles)
                    out.offset_x = p0.offset_x
                    out.offset_y = p0.offset_y
                    return
                frac = (norm - t0) / seg
                Pose.lerp_into(p0, p1, frac, out)
                return

        # Fallback: ultima posa
        last = self.keyframes[-1][1]
        out.angles.clear()
        out.angles.update(last.angles)
        out.offset_x = last.offset_x
        out.offset_y = last.offset_y


class Animator:
    """Controlla la riproduzione di Animation su uno Skeleton.

    Gestisce play, queue, speed e callback on_complete.
    """

    def __init__(self):
        self._current: Animation | None = None
        self._queue: list[tuple[Animation, float]] = []
        self._time: float = 0.0
        self._speed: float = 1.0
        self._on_complete = None
        self._finished: bool = False
        self._current_pose: Pose = Pose()

        # Blending state
        self._blend_from: Pose | None = None
        self._blend_duration: float = 0.0
        self._blend_elapsed: float = 0.0

        # Buffer riutilizzabili (zero alloc per frame)
        self._raw_buf: Pose = Pose()

    @property
    def playing(self) -> bool:
        return self._current is not None and not self._finished

    @property
    def blending(self) -> bool:
        """True se e' in corso un crossfade tra due animazioni."""
        return self._blend_from is not None

    @property
    def current_animation(self) -> Animation | None:
        return self._current

    @property
    def root_offset(self) -> tuple[float, float]:
        """Offset visivo (x, y) dalla posa corrente."""
        return self._current_pose.offset_x, self._current_pose.offset_y

    def is_finished(self) -> bool:
        """True se l'animazione corrente e' terminata."""
        return self._finished

    def get_current_time(self) -> float:
        """Ritorna il tempo corrente di riproduzione in secondi."""
        return self._time

    def get_speed(self) -> float:
        """Ritorna la velocita' di riproduzione corrente."""
        return self._speed

    def set_speed(self, speed: float) -> None:
        """Imposta la velocita' di riproduzione."""
        self._speed = speed

    def seek(self, time: float) -> None:
        """Salta a un tempo specifico nell'animazione corrente."""
        self._time = max(0.0, time)
        if self._current is not None:
            self._current.sample_into(self._time, self._current_pose)

    def get_queue_size(self) -> int:
        """Ritorna il numero di animazioni in coda."""
        return len(self._queue)

    def clear_queue(self) -> None:
        """Svuota la coda di animazioni."""
        self._queue.clear()

    def play(self, animation: Animation, speed: float = 1.0,
             on_complete=None, blend_time: float = 0.0) -> None:
        """Avvia un'animazione (sostituisce quella corrente).

        Parameters
        ----------
        blend_time : float
            Durata in secondi del crossfade dalla posa corrente alla nuova
            animazione. 0 = hard cut istantaneo (default).
        """
        if blend_time > 0 and self._current is not None:
            self._blend_from = Pose(dict(self._current_pose.angles),
                                    self._current_pose.offset_x,
                                    self._current_pose.offset_y)
            self._blend_duration = blend_time
            self._blend_elapsed = 0.0
        else:
            self._blend_from = None

        self._current = animation
        self._time = 0.0
        self._speed = speed
        self._on_complete = on_complete
        self._finished = False
        self._queue.clear()

    def queue(self, animation: Animation, blend_time: float = 0.0) -> None:
        """Accoda un'animazione dopo quella corrente.

        Parameters
        ----------
        blend_time : float
            Durata del crossfade quando questa animazione parte dalla coda.
        """
        if self._current is None:
            self.play(animation, blend_time=blend_time)
        else:
            self._queue.append((animation, blend_time))

    def stop(self) -> None:
        """Ferma l'animazione corrente."""
        self._current = None
        self._finished = True
        self._queue.clear()

    def reset(self) -> None:
        """Riporta il tempo a 0."""
        self._time = 0.0
        self._finished = False

    def update(self, dt: float) -> None:
        """Avanza il tempo e campiona la posa corrente."""
        if self._current is None or self._finished:
            return

        scaled_dt = dt * self._speed
        self._time += scaled_dt

        anim = self._current

        # Check completamento per ONCE
        if anim.loop_mode == LoopMode.ONCE and self._time >= anim.duration:
            self._time = anim.duration
            self._sample_and_blend(anim, scaled_dt)
            self._finished = True

            cb = self._on_complete
            # Avanza la coda
            if self._queue:
                next_anim, next_blend = self._queue.pop(0)
                self.play(next_anim, blend_time=next_blend)
            if cb:
                cb()
            return

        self._sample_and_blend(anim, scaled_dt)

    def _sample_and_blend(self, anim: Animation, dt: float) -> None:
        """Campiona l'animazione e applica il blend. Zero allocazioni."""
        if self._blend_from is None:
            # Nessun blend: scrivi direttamente in _current_pose
            anim.sample_into(self._time, self._current_pose)
            return

        # Blend attivo: campiona in _raw_buf, poi lerp in _current_pose
        anim.sample_into(self._time, self._raw_buf)

        self._blend_elapsed += dt
        t = min(self._blend_elapsed / self._blend_duration, 1.0)
        # Smoothstep ease in-out
        t = t * t * (3.0 - 2.0 * t)
        Pose.lerp_into(self._blend_from, self._raw_buf, t, self._current_pose)

        if self._blend_elapsed >= self._blend_duration:
            self._blend_from = None

    def apply(self, skeleton) -> None:
        """Scrive gli angoli della posa corrente sulle ossa dello skeleton."""
        for name, angle in self._current_pose.angles.items():
            bone = skeleton.get(name)
            if bone is not None:
                bone.local_angle = angle
