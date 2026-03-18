"""Mixin per il disegno di forme geometriche via GPU SDF.

Ogni forma viene renderizzata con un fragment shader dedicato che calcola
la signed distance function per-pixel, usando fwidth() per anti-aliasing
screen-space perfetto a qualsiasi angolo e scala.

Include anche draw_shape() per poligoni arbitrari (triangolazione ear-clipping).
"""

import math
import numpy as np
import moderngl

_SDF_PAD = 4.0  # design-space padding per il gradiente AA

_SHAPE_NAMES = ('circle', 'rect', 'capsule', 'triangle', 'polygon', 'star')


# ---------------------------------------------------------------------------
# Ear-clipping triangulation
# ---------------------------------------------------------------------------

def _cross_2d(ox, oy, ax, ay, bx, by):
    """Cross product of (A-O) x (B-O)."""
    return (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)


def _point_in_triangle(px, py, ax, ay, bx, by, cx, cy):
    d1 = _cross_2d(px, py, ax, ay, bx, by)
    d2 = _cross_2d(px, py, bx, by, cx, cy)
    d3 = _cross_2d(px, py, cx, cy, ax, ay)
    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (has_neg and has_pos)


def _is_ear(indices, verts, prev_i, curr_i, next_i):
    ax, ay = verts[indices[prev_i]]
    bx, by = verts[indices[curr_i]]
    cx, cy = verts[indices[next_i]]
    # Must be convex (CCW winding -> positive cross)
    if _cross_2d(ax, ay, bx, by, cx, cy) <= 0:
        return False
    # No other vertex inside this triangle
    n = len(indices)
    for i in range(n):
        if i == prev_i or i == curr_i or i == next_i:
            continue
        px, py = verts[indices[i]]
        if _point_in_triangle(px, py, ax, ay, bx, by, cx, cy):
            return False
    return True


def _triangulate(vertices):
    """Ear-clipping triangulation for a simple polygon.

    Parameters
    ----------
    vertices : list of (float, float)

    Returns
    -------
    list of (int, int, int) — triangle index triples.
    """
    n = len(vertices)
    if n < 3:
        return []
    if n == 3:
        return [(0, 1, 2)]

    # Ensure CCW winding
    area = 0.0
    for i in range(n):
        x0, y0 = vertices[i]
        x1, y1 = vertices[(i + 1) % n]
        area += (x1 - x0) * (y1 + y0)
    indices = list(range(n)) if area < 0 else list(range(n - 1, -1, -1))

    triangles = []
    while len(indices) > 2:
        ear_found = False
        m = len(indices)
        for i in range(m):
            prev_i = (i - 1) % m
            next_i = (i + 1) % m
            if _is_ear(indices, vertices, prev_i, i, next_i):
                triangles.append((indices[prev_i], indices[i], indices[next_i]))
                indices.pop(i)
                ear_found = True
                break
        if not ear_found:
            break
    return triangles


class _ShapesMixin:
    """Metodi draw_* per forme geometriche. Rendering GPU SDF."""

    def _ensure_sdf_shapes(self):
        """Lazy-init di tutti i renderer SDF: 1 VBO, N program, N VAO."""
        if self._sdf_ready:
            return

        from pyluxel.shaders import load_shader

        vert_src = load_shader('sdf_shape.vert')

        self._sdf_progs = {}
        for name in _SHAPE_NAMES:
            self._sdf_progs[name] = self.ctx.program(
                vertex_shader=vert_src,
                fragment_shader=load_shader(f'sdf_{name}.frag'),
            )

        # Quad unitario da -1 a 1 (condiviso)
        verts = np.array([
            -1, -1,  1, -1,  1, 1,
            -1, -1,  1,  1, -1, 1,
        ], dtype='f4')
        self._sdf_vbo = self.ctx.buffer(verts.tobytes())

        # Un VAO per program (ogni VAO e' legato al suo program)
        self._sdf_vaos = {}
        for name, prog in self._sdf_progs.items():
            self._sdf_vaos[name] = self.ctx.vertex_array(
                prog, [(self._sdf_vbo, '2f', 'in_pos')],
            )

        self._sdf_proj_ref = None
        self._sdf_ready = True

    def _sdf_draw(self, shape: str, cx: float, cy: float,
                  w: float, h: float, angle: float,
                  r: float, g: float, b: float, a: float,
                  **extra_uniforms):
        """Disegna una forma SDF. Generico per tutte le forme."""
        self._ensure_sdf_shapes()

        # Flush sprite batch prima di switchare shader
        if self.batch._count > 0:
            self.batch.flush()

        prog = self._sdf_progs[shape]

        # Projection: usa la camera se attiva, altrimenti default
        proj = self.renderer._view_projection if self.renderer._view_projection is not None else self.renderer.projection
        if proj is not self._sdf_proj_ref:
            self._sdf_proj_ref = proj
            proj_bytes = proj.tobytes()
            for p in self._sdf_progs.values():
                p['u_projection'].write(proj_bytes)

        pad = _SDF_PAD
        prog['u_center'] = (cx, cy)
        prog['u_half_size'] = (w * 0.5 + pad, h * 0.5 + pad)
        prog['u_shape_half'] = (w * 0.5, h * 0.5)
        prog['u_angle'] = angle
        prog['u_color'] = (r, g, b, a)

        for name, value in extra_uniforms.items():
            prog[name] = value

        self._sdf_vaos[shape].render(moderngl.TRIANGLES)

    # -- Forme --

    def draw_circle(self, x: float, y: float, radius: float,
                    r: float = 1.0, g: float = 1.0, b: float = 1.0, a: float = 1.0):
        """Cerchio. x, y = centro."""
        d = radius * 2.0
        self._sdf_draw('circle', x, y, d, d, 0.0, r, g, b, a)

    def draw_triangle(self, x: float, y: float, w: float, h: float,
                      r: float = 1.0, g: float = 1.0, b: float = 1.0, a: float = 1.0,
                      angle: float = 0.0):
        """Triangolo isoscele (punta in alto). x, y = centro."""
        self._sdf_draw('triangle', x, y, w, h, angle, r, g, b, a)

    def draw_polygon(self, x: float, y: float, radius: float, sides: int = 6,
                     r: float = 1.0, g: float = 1.0, b: float = 1.0, a: float = 1.0,
                     angle: float = 0.0):
        """Poligono regolare a N lati. x, y = centro."""
        d = radius * 2.0
        self._sdf_draw('polygon', x, y, d, d, angle, r, g, b, a,
                       u_sides=sides)

    def draw_star(self, x: float, y: float, radius: float, points: int = 5,
                  inner_ratio: float = 0.4,
                  r: float = 1.0, g: float = 1.0, b: float = 1.0, a: float = 1.0,
                  angle: float = 0.0):
        """Stella a N punte. x, y = centro. inner_ratio = raggio interno / esterno."""
        d = radius * 2.0
        self._sdf_draw('star', x, y, d, d, angle, r, g, b, a,
                       u_points=points, u_inner_ratio=inner_ratio)

    def draw_capsule(self, x: float, y: float, w: float, h: float,
                     r: float = 1.0, g: float = 1.0, b: float = 1.0, a: float = 1.0,
                     angle: float = 0.0):
        """Capsula (rettangolo con estremita' arrotondate). x, y = centro."""
        self._sdf_draw('capsule', x, y, w, h, angle, r, g, b, a)

    def draw_line(self, x1: float, y1: float, x2: float, y2: float,
                  r: float = 1.0, g: float = 1.0, b: float = 1.0, a: float = 1.0,
                  width: float = 2.0):
        """Linea da (x1, y1) a (x2, y2) con spessore e caps arrotondati."""
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length < 1e-6:
            return
        cx = (x1 + x2) * 0.5
        cy = (y1 + y2) * 0.5
        angle = math.atan2(dy, dx)
        self._sdf_draw('capsule', cx, cy, length + width, width, angle, r, g, b, a)

    # -- Custom shape (arbitrary polygon) --

    def _ensure_shape_fill(self):
        """Lazy-init del renderer per poligoni arbitrari."""
        if self._shape_fill_ready:
            return

        from pyluxel.shaders import load_shader

        self._shape_fill_prog = self.ctx.program(
            vertex_shader=load_shader('shape_fill.vert'),
            fragment_shader=load_shader('shape_fill.frag'),
        )
        # VBO dinamico — si riscrive ad ogni draw_shape()
        self._shape_fill_vbo = self.ctx.buffer(reserve=4096 * 2 * 4)  # 4096 floats
        self._shape_fill_vao = self.ctx.vertex_array(
            self._shape_fill_prog,
            [(self._shape_fill_vbo, '2f', 'in_pos')],
        )
        self._shape_fill_proj_ref = None
        self._shape_fill_cache = {}  # key -> (n_verts, np.ndarray bytes)
        self._shape_fill_ready = True

    @staticmethod
    def _shape_cache_key(vertices):
        """Hash stabile per una lista di vertici."""
        return tuple(v for pt in vertices for v in pt)

    def _build_shape_data(self, vertices, tris):
        """Costruisce il numpy array di vertici dai triangoli."""
        n_verts = len(tris) * 3
        data = np.empty(n_verts * 2, dtype='f4')
        idx = 0
        for i0, i1, i2 in tris:
            data[idx]     = vertices[i0][0]
            data[idx + 1] = vertices[i0][1]
            data[idx + 2] = vertices[i1][0]
            data[idx + 3] = vertices[i1][1]
            data[idx + 4] = vertices[i2][0]
            data[idx + 5] = vertices[i2][1]
            idx += 6
        return n_verts, data.tobytes()

    def draw_shape(self, vertices, r: float = 1.0, g: float = 1.0,
                   b: float = 1.0, a: float = 1.0):
        """Disegna un poligono arbitrario definito da vertici.

        La triangolazione viene cachata automaticamente: se i vertici non
        cambiano tra un frame e l'altro, il costo CPU e' quasi zero.

        Parameters
        ----------
        vertices : list of (float, float)
            Coordinate (x, y) in design space. Almeno 3 vertici.
            Il poligono deve essere semplice (non auto-intersecante).
        r, g, b, a : float
            Colore RGBA (0.0 – 1.0).
        """
        if len(vertices) < 3:
            return

        self._ensure_shape_fill()

        # Flush sprite batch prima di switchare shader
        if self.batch._count > 0:
            self.batch.flush()

        # Cache: triangolazione + vertex data
        key = self._shape_cache_key(vertices)
        cached = self._shape_fill_cache.get(key)
        if cached is not None:
            n_verts, byte_data = cached
        else:
            tris = _triangulate(vertices)
            if not tris:
                return
            n_verts, byte_data = self._build_shape_data(vertices, tris)
            self._shape_fill_cache[key] = (n_verts, byte_data)

        # Upload — ridimensiona il buffer se necessario
        if len(byte_data) > self._shape_fill_vbo.size:
            self._shape_fill_vbo.orphan(len(byte_data))
        self._shape_fill_vbo.write(byte_data)

        # Projection
        prog = self._shape_fill_prog
        proj = self.renderer._view_projection if self.renderer._view_projection is not None else self.renderer.projection
        if proj is not self._shape_fill_proj_ref:
            self._shape_fill_proj_ref = proj
            prog['u_projection'].write(proj.tobytes())

        prog['u_color'] = (r, g, b, a)
        self._shape_fill_vao.render(moderngl.TRIANGLES, vertices=n_verts)

    def _cleanup_shapes(self):
        """Rilascia tutte le risorse GPU SDF e shape fill."""
        from pyluxel.debug import cprint
        if self._sdf_ready:
            try:
                for vao in self._sdf_vaos.values():
                    vao.release()
                self._sdf_vbo.release()
                for prog in self._sdf_progs.values():
                    prog.release()
            except Exception as e:
                cprint.warning("App cleanup - sdf shapes:", e)
            self._sdf_ready = False
        if self._shape_fill_ready:
            try:
                self._shape_fill_vao.release()
                self._shape_fill_vbo.release()
                self._shape_fill_prog.release()
            except Exception as e:
                cprint.warning("App cleanup - shape fill:", e)
            self._shape_fill_ready = False
