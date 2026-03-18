"""Demo di draw_shape() con tema neon, ombre e bloom.

Le forme sono nere con bordi luminosi che glow grazie al bloom.
La luce principale segue il mouse.

Controls:
    Mouse       Muove la luce principale
    1           Toggle ombre on/off
    2           Cicla softness (hard / medium / soft)
"""

import math
import pygame
from pyluxel import App, Input

SOFTNESS = [0.005, 0.03, 0.08]
SOFTNESS_NAMES = ["Hard", "Medium", "Soft"]


def make_irregular_polygon(cx, cy, n, base_r, seed=0):
    """Genera un poligono irregolare a N lati con raggi variabili."""
    verts = []
    for i in range(n):
        angle = 2 * math.pi * i / n - math.pi / 2
        r = base_r * (0.6 + 0.8 * abs(math.sin(i * 2.7 + seed)))
        verts.append((cx + math.cos(angle) * r,
                      cy + math.sin(angle) * r))
    return verts


def shrink(vertices, amount):
    """Rimpicciolisce un poligono verso il suo centroide."""
    n = len(vertices)
    cx = sum(v[0] for v in vertices) / n
    cy = sum(v[1] for v in vertices) / n
    result = []
    for x, y in vertices:
        dx, dy = x - cx, y - cy
        d = math.hypot(dx, dy)
        if d > 0:
            scale = max(0, d - amount) / d
            result.append((cx + dx * scale, cy + dy * scale))
        else:
            result.append((x, y))
    return result


class CustomShapesDemo(App):

    def setup(self):
        self.ShowFPS()
        self._ambient = 0.02
        self.fx.bloom = 1.0
        self.fx.tone_mapping = "aces"

        # --- Luci ---
        self.main_light = self.add_light(
            640, 360, radius=500,
            color=(1.0, 0.95, 0.85), intensity=1.5,
            cast_shadows=True, shadow_softness=0.03)

        # Luce viola fissa
        self.add_light(
            200, 150, radius=350,
            color=(0.8, 0.2, 1.0), intensity=1.0,
            cast_shadows=True, shadow_softness=0.02,
            flicker_speed=4, flicker_amount=0.1, flicker_style="smooth")

        # Luce ciano ambientale
        self.add_light(
            1050, 550, radius=400,
            color=(0.1, 0.8, 1.0), intensity=0.6)

        # --- Forme irregolari ---

        # 1) Roccia a 13 lati asimmetrica
        rock = make_irregular_polygon(350, 320, 13, 70, seed=1)
        x, y = rock[3]
        rock[3] = (x + 50, y - 30)

        # 2) L-shape concava
        l_shape = [
            (700, 200), (800, 200), (800, 320),
            (760, 320), (760, 250), (700, 250),
        ]

        # 3) Freccia concava
        arrow = [
            (900, 350), (1000, 350), (1000, 320),
            (1080, 380), (1000, 440), (1000, 410),
            (900, 410),
        ]

        # 4) Stella irregolare
        star_pts = []
        for i in range(10):
            angle = 2 * math.pi * i / 10 - math.pi / 2
            r = 60 if i % 2 == 0 else 25 + (i * 3)
            star_pts.append((500 + math.cos(angle) * r,
                             550 + math.sin(angle) * r))

        # 5) Muro frastagliato
        jagged_wall = [
            (100, 480), (130, 460), (170, 485), (210, 455),
            (250, 480), (250, 560), (100, 560),
        ]

        # 6) Esagono allungato
        hex_shape = []
        for i in range(6):
            angle = 2 * math.pi * i / 6
            rx = 80 if i % 2 == 0 else 50
            ry = 50
            hex_shape.append((640 + math.cos(angle) * rx,
                              500 + math.sin(angle) * ry))

        # Neon border thickness
        self._border = 4

        # (vertici, colore neon HDR)
        self.shapes = [
            (rock,        (2.0, 0.4, 3.0)),    # magenta
            (l_shape,     (0.3, 3.0, 0.5)),    # verde neon
            (arrow,       (3.0, 1.5, 0.2)),    # arancio neon
            (star_pts,    (3.0, 2.5, 0.3)),    # giallo neon
            (jagged_wall, (0.3, 1.0, 3.0)),    # ciano neon
            (hex_shape,   (3.0, 0.3, 0.5)),    # rosso neon
        ]

        # Pre-calcola le versioni rimpicciolite (inner = parte nera)
        self.shapes_inner = [shrink(verts, self._border) for verts, _ in self.shapes]

        # Input
        self._soft_idx = 1
        self._shadows = True
        Input.bind("toggle_shadows", pygame.K_1)
        Input.bind("cycle_soft", pygame.K_2)

    def update(self, dt):
        self.main_light.set_position(self.mouse_x, self.mouse_y)

        if Input.pressed("toggle_shadows"):
            self._shadows = not self._shadows
            self.main_light.cast_shadows = self._shadows

        if Input.pressed("cycle_soft"):
            self._soft_idx = (self._soft_idx + 1) % len(SOFTNESS)
            self.main_light.shadow_softness = SOFTNESS[self._soft_idx]

    def draw(self):
        # Sfondo scuro
        self.draw_rect(0, 0, 1280, 720, r=0.01, g=0.01, b=0.02)

        # Neon shapes: bordo luminoso + interno nero
        for i, (verts, (cr, cg, cb)) in enumerate(self.shapes):
            # 1) Shape esterna con colore HDR (>1.0 = bloom glow)
            self.draw_shape(verts, r=cr, g=cg, b=cb)
            # 2) Shape interna nera — lascia visibile solo il bordo
            self.draw_shape(self.shapes_inner[i], r=0.0, g=0.0, b=0.0)

    def shadow_casters(self):
        for verts, _ in self.shapes:
            self.draw_shape(verts, r=1.0, g=1.0, b=1.0)

    def draw_overlay(self):
        self.draw_text("Neon Shapes + Shadows", 640, 15, size=28,
                       align_x="center")
        status = "ON" if self._shadows else "OFF"
        soft = SOFTNESS_NAMES[self._soft_idx]
        self.draw_text(f"1:Shadows={status}  2:Softness={soft}",
                       640, 695, size=14, align_x="center",
                       r=0.6, g=0.6, b=0.6)


CustomShapesDemo(1280, 720, "Neon Shapes Demo", centered=True).run()
