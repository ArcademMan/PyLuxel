"""Showcase of all post-processing and lighting effects.

Controls:
    1-8     Toggle effects
    SPACE   Shockwave at center
    Click   Shockwave at mouse
    Q/E     Exposure up/down
    T       Cycle tone mapping (ACES -> Reinhard -> None)
"""

import math
import pygame
from pyluxel import App, Input, Mouse, FalloffMode

TONE_MODES = ["aces", "reinhard", "none"]


class EffectsShowcase(App):

    def setup(self):
        self.ShowFPS()

        # Post-processing
        self._ambient = 0.08
        self.fx.bloom = 0.6
        self.fx.tone_mapping = "aces"
        self.fx.exposure = 1.0
        self.fx.vignette = 1.5

        # Toggle state for overlay
        self._tone_idx = 0

        # --- Input bindings ---
        Input.bind("toggle_bloom", pygame.K_1)
        Input.bind("toggle_ca", pygame.K_2)
        Input.bind("toggle_grain", pygame.K_3)
        Input.bind("toggle_crt", pygame.K_4)
        Input.bind("toggle_vignette", pygame.K_5)
        Input.bind("cycle_falloff", pygame.K_6)
        Input.bind("toggle_god_rays", pygame.K_7)
        Input.bind("toggle_heat_haze", pygame.K_8)
        Input.bind("cycle_tone", pygame.K_t)
        Input.bind("exposure_up", pygame.K_q)
        Input.bind("exposure_down", pygame.K_e)
        Input.bind("shockwave_center", pygame.K_SPACE)
        Input.bind("shockwave_mouse", Mouse.LEFT)

        # --- Persistent lights ---

        # Warm center point light (quadratic falloff)
        self.center_light = self.add_light(
            640, 360, radius=350,
            color=(1.0, 0.85, 0.6), intensity=1.5)

        # Red spotlight (narrow cone)
        self.spot_red = self.add_light(
            200, 200, radius=300,
            color=(1.0, 0.2, 0.1), intensity=5.2,
            is_spotlight=True, direction=135, angle=40)

        # Blue spotlight (wide cone, linear falloff)
        self.spot_blue = self.add_light(
            1080, 200, radius=280,
            color=(0.1, 0.3, 1.0), intensity=1.0,
            is_spotlight=True, direction=225, angle=60,
            falloff=FalloffMode.LINEAR)

        # Green cubic light (more concentrated)
        self.green_light = self.add_light(
            640, 550, radius=200,
            color=(0.2, 1.0, 0.4), intensity=0.8,
            falloff=FalloffMode.CUBIC)

        # Torch lights with automatic flicker (candle style)
        self.add_light(
            100, 600, radius=120,
            color=(1.0, 0.6, 0.2), intensity=0.9,
            flicker_speed=8, flicker_amount=0.4, flicker_style="candle")
        self.add_light(
            1180, 600, radius=120,
            color=(1.0, 0.6, 0.2), intensity=0.9,
            flicker_speed=8, flicker_amount=0.4, flicker_style="candle")

        # Heat haze (initially disabled)
        self._haze_active = False
        self._haze = None

    def update(self, dt):
        t = self.time

        # Move center light in a circle
        self.center_light.set_position(
            640 + math.cos(t * 0.5) * 100,
            360 + math.sin(t * 0.7) * 60)

        # Rotate spotlights
        self.spot_red.set_direction(135 + math.sin(t * 0.8) * 30)
        self.spot_blue.set_direction(225 + math.cos(t * 0.6) * 25)

        # --- Input ---
        if Input.pressed("toggle_bloom"):
            self.fx.set_bloom(0.0 if self.fx.bloom > 0 else 0.6)
        if Input.pressed("toggle_ca"):
            self.fx.set_chromatic_aberration(
                0.0 if self.fx.chromatic_aberration > 0 else 0.5)
        if Input.pressed("toggle_grain"):
            self.fx.set_film_grain(0.0 if self.fx.film_grain > 0 else 0.12)
        if Input.pressed("toggle_crt"):
            self.fx.set_crt(not self.fx.crt)
        if Input.pressed("toggle_vignette"):
            self.fx.set_vignette(0.0 if self.fx.vignette > 0 else 1.5)
        if Input.pressed("cycle_falloff"):
            modes = [FalloffMode.LINEAR, FalloffMode.QUADRATIC, FalloffMode.CUBIC]
            idx = (modes.index(self.green_light.falloff) + 1) % 3
            self.green_light.set_falloff(modes[idx])

        if Input.pressed("toggle_god_rays"):
            self.fx.set_god_rays(0.0 if self.fx.god_rays > 0 else 0.5)

        if Input.pressed("toggle_heat_haze"):
            self._haze_active = not self._haze_active
            if self._haze_active:
                self._haze = self.add_heat_haze(
                    500, 450, width=280, height=80,
                    strength=0.004, speed=3.0, scale=18.0)
            else:
                if self._haze:
                    self.remove_heat_haze(self._haze)
                    self._haze = None

        if Input.pressed("cycle_tone"):
            self._tone_idx = (self._tone_idx + 1) % 3
            self.fx.set_tone_mapping(TONE_MODES[self._tone_idx])

        if Input.held("exposure_up"):
            self.fx.set_exposure(min(self.fx.exposure + dt, 3.0))
        if Input.held("exposure_down"):
            self.fx.set_exposure(max(self.fx.exposure - dt, 0.1))

        if Input.pressed("shockwave_center"):
            self.add_shockwave(640, 360, max_radius=350, strength=0.06)

        if Input.pressed("shockwave_mouse"):
            self.add_shockwave(self.mouse_x, self.mouse_y,
                               max_radius=250, strength=0.05)

    def draw(self):
        t = self.time

        # Dark floor with checkerboard pattern
        for x in range(0, 1280, 64):
            for y in range(0, 720, 64):
                shade = 0.03 + ((x // 64 + y // 64) % 2) * 0.02
                self.draw_rect(x, y, 64, 64, r=shade, g=shade, b=shade + 0.01)

        # Bright circles (HDR > 1.0 to test bloom)
        self.draw_circle(640 + math.cos(t) * 80, 360 + math.sin(t) * 50,
                         radius=20, r=2.0, g=1.8, b=1.0)
        self.draw_circle(300, 400, radius=15, r=1.5, g=0.3, b=0.3)
        self.draw_circle(980, 400, radius=15, r=0.3, g=0.3, b=1.5)

        # Colored rectangles
        self.draw_rect(580, 500, 120, 30, r=0.8, g=0.2, b=0.2)
        self.draw_rect(580, 540, 120, 30, r=0.2, g=0.8, b=0.2)
        self.draw_rect(580, 580, 120, 30, r=0.2, g=0.2, b=0.8)

        # Rotating stars
        self.draw_star(200, 360, radius=35, points=5,
                       r=1.0, g=0.9, b=0.2, angle=t)
        self.draw_star(1080, 360, radius=35, points=6,
                       r=0.2, g=0.8, b=1.0, angle=-t * 0.7)

        # Capsules (pillars)
        self.draw_capsule(80, 300, w=30, h=200, r=0.15, g=0.12, b=0.1)
        self.draw_capsule(1170, 300, w=30, h=200, r=0.15, g=0.12, b=0.1)

    def draw_overlay(self):
        self.draw_text("PyLuxel Effects Showcase", 640, 15,
                       size=28, align_x="center")

        y = 680
        on = (0.2, 1.0, 0.3, 0.9)
        off = (0.5, 0.5, 0.5, 0.5)

        effects = [
            ("1:Bloom", self.fx.bloom > 0),
            ("2:ChromAb", self.fx.chromatic_aberration > 0),
            ("3:Grain", self.fx.film_grain > 0),
            ("4:CRT", self.fx.crt),
            ("5:Vignette", self.fx.vignette > 0),
            (f"6:Falloff({self.green_light.falloff.name[:3]})", True),
            ("7:GodRays", self.fx.god_rays > 0),
            ("8:HeatHaze", self._haze_active),
        ]

        x = 20
        for label, active in effects:
            c = on if active else off
            self.draw_text(label, x, y, size=13, r=c[0], g=c[1], b=c[2], a=c[3])
            x += 140

        self.draw_text(
            f"T:ToneMap={self.fx.tone_mapping}  Q/E:Exposure={self.fx.exposure:.1f}  "
            f"SPACE/Click:Shockwave",
            640, 705, size=12, align_x="center", r=0.5, g=0.5, b=0.5)


EffectsShowcase(1280, 720, "Effects Showcase", centered=True).run()
