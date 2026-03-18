import numpy as np
import moderngl
from pyluxel.shaders import load_shader
from pyluxel.debug import cprint


class RoundedRectRenderer:
    """Disegna rettangoli con angoli arrotondati via SDF shader GPU."""

    def __init__(self, ctx: moderngl.Context, projection: np.ndarray):
        self.ctx = ctx
        self.prog = ctx.program(
            vertex_shader=load_shader("ui_rect.vert"),
            fragment_shader=load_shader("ui_rect.frag"),
        )
        self.prog["u_projection"].write(projection.tobytes())

        # Quad riutilizzabile (aggiornato ad ogni draw)
        self._quad_data = np.zeros(4 * 4, dtype="f4")  # 4 verts * (pos2 + uv2)
        self._vbo = ctx.buffer(reserve=self._quad_data.nbytes, dynamic=True)
        indices = np.array([0, 1, 2, 2, 3, 0], dtype="i4")
        self._ibo = ctx.buffer(indices.tobytes())
        self._vao = ctx.vertex_array(
            self.prog,
            [(self._vbo, "2f 2f", "in_position", "in_uv")],
            index_buffer=self._ibo,
        )

    def draw(self, x: float, y: float, w: float, h: float, radius: float,
             r: float = 1.0, g: float = 1.0, b: float = 1.0, a: float = 1.0):
        """Disegna un rettangolo arrotondato. Coordinate in design space."""
        # Limita il raggio al massimo possibile
        max_r = min(w, h) * 0.5
        radius = min(radius, max_r)

        # Aggiorna vertici del quad
        self._quad_data[:] = [
            x,     y + h,  0, 0,  # bottom-left
            x + w, y + h,  1, 0,  # bottom-right
            x + w, y,      1, 1,  # top-right
            x,     y,      0, 1,  # top-left
        ]
        self._vbo.write(self._quad_data.tobytes())

        # Uniforms
        self.prog["u_color"].value = (r, g, b, a)
        self.prog["u_size"].value = (w, h)
        self.prog["u_radius"].value = radius

        self._vao.render(moderngl.TRIANGLES)

        from pyluxel.debug.gpu_stats import GPUStats
        GPUStats.record_draw()

    def release(self):
        for obj in (self._vao, self._vbo, self._ibo, self.prog):
            try:
                obj.release()
            except Exception as e:
                cprint.warning("GPU release failed:", e)
