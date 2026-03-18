"""Colored rectangles + persistent lights -- subclass pattern."""

import math
from pyluxel import App


class Rectangles(App):
    def setup(self):
        self.ShowFPS()
        self.set_post_process(ambient=0.05, vignette=2.0, bloom=1.8)

        # Fixed lights -- created once, persist forever
        self.add_light(160, 240, radius=1250, color=(1.0, 0.3, 0.2), intensity=1.2)
        self.add_light(410, 240, radius=250, color=(0.2, 1.0, 0.3), intensity=1.2)
        self.add_light(660, 240, radius=250, color=(0.3, 0.3, 1.0), intensity=1.2)

        # This light will follow the orbiting rectangle
        self.orbit_light = self.add_light(0, 0, radius=200, color=(1.0, 0.9, 0.4), intensity=1.5)

    def update(self, dt):
        # Move the orbiting light
        angle = self.time * 1.5
        self.orbit_light.x = 640 + math.cos(angle) * 150
        self.orbit_light.y = 400 + math.sin(angle) * 150

    def draw(self):
        self.draw_rect(350, 200, 120, 80, r=0.1, g=1.0, b=0.1)
        self.draw_rect(600, 200, 120, 80, r=0.1, g=0.2, b=1.0)

        # Orbiting yellow rectangle
        cx, cy = 640, 400
        angle = self.time * 1.5
        ox = cx + math.cos(angle) * 150
        oy = cy + math.sin(angle) * 150
        self.draw_rect(ox - 25, oy - 25, 50, 50, r=1.0, g=0.9, b=0.2)
        self.draw_text("Test", 640, 350, size=40, align_x="center")

    def draw_overlay(self):
        # Overlay text -- flat, not affected by lights
        self.draw_rect(100, 200, 120, 80, r=1.0, g=0.1, b=0.1)
        self.draw_text("PyLuxel Engine", 640, 50, size=40, align_x="center")


Rectangles(1280, 720, "Rectangles + Lights").run()
