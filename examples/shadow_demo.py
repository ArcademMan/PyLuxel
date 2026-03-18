"""Demo del sistema di ombre 2D.

La luce segue il mouse e proietta ombre dai muri.

Controls:
    Click       Sposta la luce (segue il mouse)
    1           Toggle shadow on/off
    2           Cicla softness (hard -> medium -> soft)
    Q/E         Raggio +/-
"""

import pygame
from pyluxel import App, Input, Mouse, FalloffMode

SOFTNESS_LEVELS = [0.005, 0.03, 0.08]
SOFTNESS_NAMES = ["Hard", "Medium", "Soft"]


class ShadowDemo(App):

    def setup(self):
        self.ShowFPS()
        self._ambient = 0.05
        self.fx.bloom = 0.4
        self.fx.tone_mapping = "aces"

        # Luce principale che segue il mouse (con ombre)
        self.main_light = self.add_light(
            640, 360, radius=400,
            color=(1.0, 0.9, 0.7), intensity=1.8,
            cast_shadows=True, shadow_softness=0.03)

        # Luce ambientale blu (senza ombre)
        self.add_light(640, 100, radius=600,
                       color=(0.1, 0.15, 0.3), intensity=0.4)

        # Torcia decorativa (senza ombre, con flicker)
        self.add_light(275, 200, radius=420,
                       color=(1.0, 0.8, 0.4), intensity=1.8,
                       flicker_speed=8, flicker_amount=0.2,
                       flicker_style="candle", cast_shadows=True)

        # Muri
        self.walls = [
            (300, 200, 40, 250),   # pilastro sinistro
            (600, 150, 200, 30),   # muro orizzontale alto
            (900, 300, 40, 200),   # pilastro destro
            (400, 500, 300, 30),   # muro orizzontale basso
            (150, 400, 30, 150),   # muro laterale
            (1050, 450, 150, 30),  # mensola destra
        ]

        self._softness_idx = 1
        self._shadows_on = True

        # Input
        Input.bind("toggle_shadows", pygame.K_1)
        Input.bind("cycle_softness", pygame.K_2)
        Input.bind("radius_up", pygame.K_q)
        Input.bind("radius_down", pygame.K_e)

    def update(self, dt):
        # Luce segue il mouse
        self.main_light.set_position(self.mouse_x, self.mouse_y)

        if Input.pressed("toggle_shadows"):
            self._shadows_on = not self._shadows_on
            self.main_light.cast_shadows = self._shadows_on

        if Input.pressed("cycle_softness"):
            self._softness_idx = (self._softness_idx + 1) % len(SOFTNESS_LEVELS)
            self.main_light.shadow_softness = SOFTNESS_LEVELS[self._softness_idx]

        if Input.held("radius_up"):
            self.main_light.set_radius(
                min(self.main_light.radius + 200 * dt, 800))
        if Input.held("radius_down"):
            self.main_light.set_radius(
                max(self.main_light.radius - 200 * dt, 80))

    def draw(self):
        # Pavimento scacchiera scura
        for x in range(0, 1280, 64):
            for y in range(0, 720, 64):
                shade = 0.04 + ((x // 64 + y // 64) % 2) * 0.02
                self.draw_rect(x, y, 64, 64, r=shade, g=shade, b=shade + 0.01)

        # Muri visibili
        for wx, wy, ww, wh in self.walls:
            self.draw_rect(wx, wy, ww, wh, r=0.25, g=0.2, b=0.18)

    def shadow_casters(self):
        # Disegna i muri come occluder (bianco = blocca luce)
        for wx, wy, ww, wh in self.walls:
            self.draw_rect(wx, wy, ww, wh, r=1.0, g=1.0, b=1.0)

    def draw_overlay(self):
        self.draw_text("Shadow Demo", 640, 15, size=28, align_x="center")

        shadow_status = "ON" if self._shadows_on else "OFF"
        soft_name = SOFTNESS_NAMES[self._softness_idx]
        radius = int(self.main_light.radius)

        self.draw_text(
            f"1:Shadows={shadow_status}  2:Softness={soft_name}  "
            f"Q/E:Radius={radius}",
            640, 695, size=14, align_x="center",
            r=0.6, g=0.6, b=0.6)


ShadowDemo(1280, 720, "Shadow Demo", centered=True).run()
