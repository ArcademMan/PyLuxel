"""pyluxel.physics.collision -- Primitive di collisione 2D.

Funzioni pure (no side-effect) per test di intersezione tra forme
geometriche comuni nei giochi 2D: AABB, cerchi, raggi.
"""

import math

__all__ = [
    "aabb_vs_aabb",
    "aabb_vs_point",
    "aabb_vs_circle",
    "circle_vs_circle",
    "circle_vs_point",
    "ray_vs_aabb",
    "aabb_overlap",
]


# ── AABB ────────────────────────────────────────────────────────────

def aabb_vs_aabb(x1: float, y1: float, w1: float, h1: float,
                 x2: float, y2: float, w2: float, h2: float) -> bool:
    """Test di intersezione tra due AABB (x, y = top-left).

    Returns:
        True se i due rettangoli si sovrappongono.
    """
    return (x1 < x2 + w2 and x1 + w1 > x2 and
            y1 < y2 + h2 and y1 + h1 > y2)


def aabb_vs_point(rx: float, ry: float, rw: float, rh: float,
                  px: float, py: float) -> bool:
    """True se il punto (px, py) e' dentro l'AABB."""
    return rx <= px <= rx + rw and ry <= py <= ry + rh


def aabb_overlap(x1: float, y1: float, w1: float, h1: float,
                 x2: float, y2: float, w2: float, h2: float
                 ) -> tuple[float, float] | None:
    """Calcola il vettore di penetrazione minimo tra due AABB.

    Returns:
        (dx, dy) per risolvere la collisione spostando il primo AABB,
        oppure None se non c'e' collisione.
    """
    ox = min(x1 + w1, x2 + w2) - max(x1, x2)
    oy = min(y1 + h1, y2 + h2) - max(y1, y2)
    if ox <= 0 or oy <= 0:
        return None

    # Asse di minima penetrazione
    cx1 = x1 + w1 * 0.5
    cx2 = x2 + w2 * 0.5
    cy1 = y1 + h1 * 0.5
    cy2 = y2 + h2 * 0.5

    if ox < oy:
        return (-ox if cx1 < cx2 else ox, 0.0)
    else:
        return (0.0, -oy if cy1 < cy2 else oy)


# ── Cerchi ──────────────────────────────────────────────────────────

def circle_vs_circle(x1: float, y1: float, r1: float,
                     x2: float, y2: float, r2: float) -> bool:
    """True se i due cerchi si sovrappongono."""
    dx = x2 - x1
    dy = y2 - y1
    dist_sq = dx * dx + dy * dy
    radii = r1 + r2
    return dist_sq <= radii * radii


def circle_vs_point(cx: float, cy: float, radius: float,
                    px: float, py: float) -> bool:
    """True se il punto e' dentro il cerchio."""
    dx = px - cx
    dy = py - cy
    return dx * dx + dy * dy <= radius * radius


def aabb_vs_circle(rx: float, ry: float, rw: float, rh: float,
                   cx: float, cy: float, radius: float) -> bool:
    """True se l'AABB e il cerchio si sovrappongono."""
    # Punto piu' vicino dell'AABB al centro del cerchio
    closest_x = max(rx, min(cx, rx + rw))
    closest_y = max(ry, min(cy, ry + rh))
    dx = cx - closest_x
    dy = cy - closest_y
    return dx * dx + dy * dy <= radius * radius


# ── Ray ─────────────────────────────────────────────────────────────

def ray_vs_aabb(ox: float, oy: float, dx: float, dy: float,
                rx: float, ry: float, rw: float, rh: float
                ) -> float | None:
    """Intersezione raggio-AABB con parametro t in [0, 1].

    Il raggio va da (ox, oy) a (ox+dx, oy+dy).

    Args:
        ox, oy: origine del raggio
        dx, dy: direzione * lunghezza (il raggio termina a ox+dx, oy+dy)
        rx, ry: top-left dell'AABB
        rw, rh: dimensioni dell'AABB

    Returns:
        Il parametro t (0-1) del primo punto di contatto,
        oppure None se non c'e' intersezione.
    """
    tmin = 0.0
    tmax = 1.0
    for axis in range(2):
        o = ox if axis == 0 else oy
        d = dx if axis == 0 else dy
        rmin = rx if axis == 0 else ry
        rmax = (rx + rw) if axis == 0 else (ry + rh)
        if abs(d) < 1e-9:
            if o < rmin or o > rmax:
                return None
        else:
            t1 = (rmin - o) / d
            t2 = (rmax - o) / d
            if t1 > t2:
                t1, t2 = t2, t1
            tmin = max(tmin, t1)
            tmax = min(tmax, t2)
            if tmin > tmax:
                return None
    return tmin


# ── Collisione con lista di muri ────────────────────────────────────

def collides_aabb_list(x: float, y: float, half: float,
                       walls: list[tuple[float, float, float, float]]
                       ) -> bool:
    """Test rapido: un quadrato centrato in (x, y) con semi-lato `half`
    collide con almeno un muro della lista?

    Ogni muro e' una tupla (rx, ry, rw, rh).
    """
    for wx, wy, ww, wh in walls:
        if (x + half > wx and x - half < wx + ww and
                y + half > wy and y - half < wy + wh):
            return True
    return False
