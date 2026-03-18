"""Procedural fog layer with wind — standalone fullscreen effect."""

from pyluxel.shaders import load_shader
from pyluxel.debug import cprint
import numpy as np
import moderngl


class FogLayer:
    """Fullscreen procedural fog rendered via simplex FBM noise.

    Self-contained: only needs a ModernGL context.
    Render it inside a scene FBO with alpha blending enabled so
    the lighting pass illuminates the fog naturally.
    """

    def __init__(self, ctx: moderngl.Context):
        self.ctx = ctx

        # Stato persistente con valori di default
        self._color = (0.6, 0.6, 0.65)
        self._density = 0.4
        self._scale = 3.0
        self._wind_speed = (0.5, 0.1)
        self._height_falloff = 0.0

        self.prog = ctx.program(
            vertex_shader=load_shader("screen.vert"),
            fragment_shader=load_shader("fog.frag"),
        )

        vertices = np.array([
            # x     y     u    v
            -1.0, -1.0,  0.0, 0.0,
             1.0, -1.0,  1.0, 0.0,
            -1.0,  1.0,  0.0, 1.0,
             1.0,  1.0,  1.0, 1.0,
        ], dtype="f4")

        self.vbo = ctx.buffer(vertices.tobytes())
        self.vao = ctx.vertex_array(
            self.prog,
            [(self.vbo, "2f 2f", "in_position", "in_uv")],
        )

    def set_color(self, r: float, g: float, b: float):
        """Imposta il colore della nebbia."""
        self._color = (r, g, b)

    def set_density(self, density: float):
        """Imposta la densita' della nebbia."""
        self._density = density

    def set_wind_speed(self, vx: float, vy: float):
        """Imposta la velocita' del vento."""
        self._wind_speed = (vx, vy)

    def set_scale(self, scale: float):
        """Imposta la scala del pattern."""
        self._scale = scale

    def set_height_falloff(self, falloff: float):
        """Imposta il falloff verticale (0=uniforme, >0=piu' denso in basso)."""
        self._height_falloff = falloff

    def get_color(self) -> tuple:
        """Ritorna il colore della nebbia."""
        return self._color

    def get_density(self) -> float:
        """Ritorna la densita' della nebbia."""
        return self._density

    def get_wind_speed(self) -> tuple:
        """Ritorna la velocita' del vento."""
        return self._wind_speed

    def render(self, time: float,
               color: tuple = (0.6, 0.6, 0.65),
               density: float = 0.4,
               scale: float = 3.0,
               sparsity: float = 0.0,
               height_falloff: float = 0.0,
               wind_speed: tuple = (0.5, 0.1),
               design_size: tuple = (1280, 720)):
        """Draw the fog quad. Call while a scene FBO with blending is active.

        Args:
            height_falloff: 0=uniforme, >0 = esponenziale (piu' denso in basso).
                            Valori consigliati: 0.0-3.0.
        """
        self.prog["u_time"].value = time
        self.prog["u_wind_speed"].value = wind_speed
        self.prog["u_color"].value = color
        self.prog["u_density"].value = density
        self.prog["u_scale"].value = scale
        self.prog["u_sparsity"].value = sparsity
        self.prog["u_height_falloff"].value = height_falloff
        self.prog["u_resolution"].value = design_size

        self.vao.render(moderngl.TRIANGLE_STRIP)

        from pyluxel.debug.gpu_stats import GPUStats
        GPUStats.record_draw()

    def release(self):
        """Free GPU resources."""
        for obj in (self.vao, self.vbo, self.prog):
            try:
                obj.release()
            except Exception as e:
                cprint.warning("GPU release failed:", e)
