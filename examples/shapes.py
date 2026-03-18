"""All available shapes -- circles, triangles, polygons, stars, capsules."""

import math
from pyluxel import App


class Shapes(App):
    def setup(self):
        self.set_post_process(ambient=0.2, vignette=1.0, bloom=0.2, tone_mapping="reinhard")
        self.add_light(1060, 200, radius=250, color=(0.2, 1.0, 0.3), intensity=1.2)
        self.ShowFPS()

    def draw(self):
        y = 200

        # Circle
        self.draw_circle(120, y, radius=50, r=1.0, g=0.2, b=0.2)

        # Triangle
        self.draw_triangle(280, y, w=90, h=100, r=0.2, g=1.0, b=0.2)

        # Pentagon
        self.draw_polygon(440, y, radius=55, sides=5, r=0.2, g=0.4, b=1.0)

        # Hexagon
        self.draw_polygon(600, y, radius=55, sides=6, r=1.0, g=0.6, b=0.1)

        # Octagon
        self.draw_polygon(760, y, radius=55, sides=8, r=0.8, g=0.2, b=0.8)

        # 5-pointed star
        self.draw_star(920, y, radius=55, points=5, r=1.0, g=0.9, b=0.1)

        # 8-pointed star (less pointy)
        self.draw_star(1080, y, radius=55, points=8, inner_ratio=0.6, r=0.1, g=0.9, b=0.9)

        y2 = 420

        # Horizontal capsule
        self.draw_capsule(200, y2, w=180, h=50, r=0.9, g=0.3, b=0.5)

        # Vertical capsule
        self.draw_capsule(420, y2, w=50, h=140, r=0.3, g=0.7, b=0.9)

        # Rotating triangle
        angle = self.time * 2
        self.draw_triangle(640, y2, w=80, h=90, r=0.2, g=1.0, b=0.5, angle=angle)

        # Rotating star
        self.draw_star(860, y2, radius=60, points=6, r=1.0, g=0.5, b=0.0, angle=-angle)

        # Pulsing circle
        pulse = 30 + math.sin(self.time * 3) * 15
        self.draw_circle(1060, y2, radius=pulse, r=0.5, g=0.3, b=1.0)

    def draw_overlay(self):
        self.draw_text("PyLuxel Shapes", 640, 30, size=36, align_x="center")
        self.draw_text("circle / triangle / polygon / star / capsule", 640, 680,
                       size=16, align_x="center", r=0.6, g=0.6, b=0.6)


Shapes(1280, 720, "Shapes Demo").run()
