import math
import numpy as np
import moderngl

from pyluxel.debug import cprint


class SpriteBatch:
    """Accumula sprite e li disegna in un singolo draw call per texture."""

    MAX_SPRITES = 4096

    def __init__(self, ctx: moderngl.Context, sprite_prog: moderngl.Program):
        self.ctx = ctx
        self.prog = sprite_prog

        # Ogni sprite = 4 vertici = quad
        # Ogni vertice: pos(2f) + uv(2f) + color(4f) = 8 float
        floats_per_vertex = 8
        verts_per_sprite = 4
        self._vertex_data = np.zeros(
            self.MAX_SPRITES * verts_per_sprite * floats_per_vertex, dtype="f4")

        self._vbo = ctx.buffer(reserve=self._vertex_data.nbytes, dynamic=True)

        # Index buffer: 2 triangoli per sprite (0,1,2, 2,3,0)
        indices = []
        for i in range(self.MAX_SPRITES):
            base = i * 4
            indices.extend([base, base + 1, base + 2,
                            base + 2, base + 3, base])
        self._ibo = ctx.buffer(np.array(indices, dtype="i4").tobytes())

        self._vao = ctx.vertex_array(
            sprite_prog,
            [(self._vbo, "2f 2f 4f", "in_position", "in_uv", "in_color")],
            index_buffer=self._ibo,
        )

        self._count = 0
        self._current_texture = None

    def begin(self, texture: moderngl.Texture):
        """Inizia un batch con una texture."""
        self._count = 0
        self._current_texture = texture

    def draw(self, x: float, y: float, w: float, h: float,
             u0: float = 0.0, v0: float = 0.0,
             u1: float = 1.0, v1: float = 1.0,
             r: float = 1.0, g: float = 1.0,
             b: float = 1.0, a: float = 1.0,
             angle: float = 0.0):
        """Aggiunge uno sprite al batch. angle in radianti, rotazione attorno al centro."""
        if self._count >= self.MAX_SPRITES:
            self.flush()

        i = self._count * 32  # 4 verts * 8 floats

        if angle == 0.0:
            # Fast path: nessuna rotazione
            self._vertex_data[i:i + 8] = [x, y + h, u0, v0, r, g, b, a]
            self._vertex_data[i + 8:i + 16] = [x + w, y + h, u1, v0, r, g, b, a]
            self._vertex_data[i + 16:i + 24] = [x + w, y, u1, v1, r, g, b, a]
            self._vertex_data[i + 24:i + 32] = [x, y, u0, v1, r, g, b, a]
        else:
            cx = x + w * 0.5
            cy = y + h * 0.5
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            dx = w * 0.5 * cos_a
            dy = w * 0.5 * sin_a
            ex = h * 0.5 * sin_a
            ey = h * 0.5 * cos_a

            # Bottom-left
            self._vertex_data[i:i + 8] = [
                cx - dx - ex, cy - dy + ey, u0, v0, r, g, b, a]
            # Bottom-right
            self._vertex_data[i + 8:i + 16] = [
                cx + dx - ex, cy + dy + ey, u1, v0, r, g, b, a]
            # Top-right
            self._vertex_data[i + 16:i + 24] = [
                cx + dx + ex, cy + dy - ey, u1, v1, r, g, b, a]
            # Top-left
            self._vertex_data[i + 24:i + 32] = [
                cx - dx + ex, cy - dy - ey, u0, v1, r, g, b, a]

        self._count += 1

    def flush(self):
        """Invia i dati alla GPU e disegna."""
        if self._count == 0:
            return

        self._vbo.write(self._vertex_data[:self._count * 32].tobytes())

        if self._current_texture:
            self._current_texture.use(0)
            self.prog["u_texture"].value = 0

        self._vao.render(moderngl.TRIANGLES, vertices=self._count * 6)

        from pyluxel.debug.gpu_stats import GPUStats
        GPUStats.record_draw(self._count)

        self._count = 0

    def get_sprite_count(self) -> int:
        """Ritorna il numero di sprite in coda prima del flush."""
        return self._count

    def clear(self):
        """Scarta gli sprite in coda senza inviarli alla GPU."""
        self._count = 0

    def release(self):
        """Rilascia le risorse GPU (VBO, IBO, VAO)."""
        for obj in (self._vao, self._vbo, self._ibo):
            try:
                obj.release()
            except Exception as e:
                cprint.warning(e)

    def end(self):
        """Conclude il batch e disegna tutto ciò che resta."""
        self.flush()
        self._current_texture = None
