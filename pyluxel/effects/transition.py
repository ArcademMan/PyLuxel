"""Scene transition effects — fade, dissolve, wipe, diamond."""

from pyluxel.shaders import load_shader
from pyluxel.debug import cprint
import numpy as np
import moderngl


class TransitionMode:
    """Modi di transizione disponibili."""
    FADE = 0
    DISSOLVE = 1
    WIPE_LEFT = 2
    WIPE_DOWN = 3
    DIAMOND = 4


class Transition:
    """Gestisce transizioni tra scene con effetti visivi.

    Usare come overlay dopo il post-processing per coprire
    gradualmente lo schermo con un effetto.

    Esempio::

        transition = Transition(ctx)

        # Inizia transizione out (scena -> nero)
        transition.start(TransitionMode.DISSOLVE, duration=0.5)

        # Nel game loop
        if transition.active:
            transition.update(dt)
            transition.render()

            if transition.done:
                # Cambia scena, poi fai transizione in
                transition.start(TransitionMode.DISSOLVE, duration=0.5, reverse=True)
    """

    def __init__(self, ctx: moderngl.Context):
        self.ctx = ctx

        self.prog = ctx.program(
            vertex_shader=load_shader("screen.vert"),
            fragment_shader=load_shader("transition.frag"),
        )

        vertices = np.array([
            -1.0, -1.0,  0.0, 0.0,
             1.0, -1.0,  1.0, 0.0,
            -1.0,  1.0,  0.0, 1.0,
             1.0,  1.0,  1.0, 1.0,
        ], dtype="f4")

        self._vbo = ctx.buffer(vertices.tobytes())
        self._vao = ctx.vertex_array(
            self.prog,
            [(self._vbo, "2f 2f", "in_position", "in_uv")],
        )

        self._mode = TransitionMode.FADE
        self._duration = 1.0
        self._elapsed = 0.0
        self._reverse = False
        self._active = False
        self._color = (0.0, 0.0, 0.0)
        self._callback = None
        self._paused = False

    @property
    def active(self) -> bool:
        """True se una transizione e' in corso."""
        return self._active

    @property
    def done(self) -> bool:
        """True se la transizione ha raggiunto la fine."""
        return self._active and self._elapsed >= self._duration

    @property
    def progress(self) -> float:
        """Progresso corrente (0.0 -> 1.0)."""
        if self._duration <= 0:
            return 1.0
        p = min(self._elapsed / self._duration, 1.0)
        return 1.0 - p if self._reverse else p

    def get_mode(self) -> int:
        """Ritorna il modo di transizione corrente."""
        return self._mode

    def get_duration(self) -> float:
        """Ritorna la durata della transizione in secondi."""
        return self._duration

    def get_elapsed(self) -> float:
        """Ritorna il tempo trascorso della transizione."""
        return self._elapsed

    def is_reverse(self) -> bool:
        """True se la transizione e' un fade-in (reverse)."""
        return self._reverse

    def pause(self):
        """Mette in pausa la transizione."""
        self._paused = True

    def resume(self):
        """Riprende la transizione dopo una pausa."""
        self._paused = False

    def start(self, mode: int = TransitionMode.FADE, duration: float = 1.0,
              color: tuple = (0.0, 0.0, 0.0), reverse: bool = False,
              on_complete=None):
        """Avvia una transizione.

        Args:
            mode: TransitionMode.FADE/DISSOLVE/WIPE_LEFT/WIPE_DOWN/DIAMOND
            duration: durata in secondi
            color: colore target (default nero)
            reverse: True per andare da colore a scena (fade-in)
            on_complete: callback chiamato al termine
        """
        self._mode = mode
        self._duration = max(0.01, duration)
        self._elapsed = 0.0
        self._reverse = reverse
        self._active = True
        self._color = color
        self._callback = on_complete

    def stop(self):
        """Ferma la transizione immediatamente."""
        self._active = False
        self._callback = None

    def update(self, dt: float):
        """Aggiorna il timer della transizione."""
        if not self._active or self._paused:
            return

        self._elapsed += dt
        if self._elapsed >= self._duration:
            self._elapsed = self._duration
            if self._callback:
                cb = self._callback
                self._callback = None
                cb()

    def render(self, screen_texture: moderngl.Texture,
               screen_width: int, screen_height: int):
        """Renderizza l'effetto di transizione sopra lo schermo.

        Chiamare dopo post_process() e begin_screen_overlay().

        Args:
            screen_texture: la texture dello schermo corrente
            screen_width: larghezza finestra
            screen_height: altezza finestra
        """
        if not self._active:
            return

        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

        screen_texture.use(0)
        self.prog["u_texture"].value = 0
        self.prog["u_progress"].value = self.progress
        self.prog["u_mode"].value = self._mode
        self.prog["u_color"].value = self._color
        self.prog["u_resolution"].value = (float(screen_width), float(screen_height))

        self._vao.render(moderngl.TRIANGLE_STRIP)

        from pyluxel.debug.gpu_stats import GPUStats
        GPUStats.record_draw()

    def release(self):
        """Rilascia risorse GPU."""
        for obj in (self._vao, self._vbo, self.prog):
            try:
                obj.release()
            except Exception as e:
                cprint.warning("GPU release failed:", e)
