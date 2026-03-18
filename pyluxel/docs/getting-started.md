# Getting Started

Minimal setup to get a PyLuxel window running.

---

## Option 1: App Bootstrap (Recommended)

The `App` class handles everything automatically: window, OpenGL context, renderer, sprite batch, lighting, input, and the game loop.

### Decorator Pattern

```python
from pyluxel import App, Input
import pygame

app = App(1280, 720, "My Game")

# Bind input actions
Input.bind("quit", pygame.K_ESCAPE)

@app.on_update
def update(dt):
    if Input.pressed("quit"):
        app.quit()

@app.on_draw
def draw():
    app.draw_rect(100, 100, 50, 50, r=1, g=0, b=0)
    app.draw_text("Hello PyLuxel!", 640, 360, size=32, align_x="center")

app.run()
```

### Subclass Pattern

```python
from pyluxel import App, Input
import pygame

class MyGame(App):
    def setup(self):
        self.player_x = 100
        Input.bind("right", pygame.K_d, pygame.K_RIGHT)
        Input.bind("left", pygame.K_a, pygame.K_LEFT)

    def update(self, dt):
        if Input.held("right"):
            self.player_x += 200 * dt
        if Input.held("left"):
            self.player_x -= 200 * dt

    def draw(self):
        self.draw_rect(self.player_x, 300, 32, 32, r=0, g=1, b=0)

MyGame(1280, 720, "My Game").run()
```

### App Constructor

```python
App(
    width=1280,              # window width
    height=720,              # window height
    title="PyLuxel",         # window title
    design_width=None,       # virtual resolution width (defaults to width)
    design_height=None,      # virtual resolution height (defaults to height)
    fps=60,                  # frame rate cap
    vsync=False,             # vertical sync
    resizable=False,         # allow window resizing
    centered=False,          # center window on screen
    clear_color=(0.05, 0.04, 0.07),  # background clear color (RGB 0-1)
)
```

---

## Option 2: Manual Setup

For full control over the rendering pipeline.

```python
import pygame
import moderngl
from pyluxel import (
    R, Resolution, Renderer, SpriteBatch, TextureManager,
    Camera, LightingSystem, FontManager, SDFFontCache,
    Input, PostFX,
)

# 1. Initialize pygame + OpenGL
pygame.init()
screen = pygame.display.set_mode((1280, 720), pygame.OPENGL | pygame.DOUBLEBUF)
ctx = moderngl.create_context()

# 2. Resolution singleton
R.init(1280, 720)
R.set_resolution(1280, 720)

# 3. Renderer (HDR FBO pipeline)
renderer = Renderer(ctx, 1280, 720, design_width=1280, design_height=720)

# 4. Sprite batch
batch = SpriteBatch(ctx, renderer.sprite_prog)

# 5. Textures
textures = TextureManager(ctx, "assets/sprites")
white_tex = textures.create_from_color(1, 1)
player_tex = textures.load("player")  # loads assets/sprites/player.png

# 6. Fonts
FontManager.init("assets/fonts", font_files={
    "body": "Inter-Regular.ttf",
    "title": "Inter-Bold.ttf",
})
fonts = SDFFontCache(ctx, renderer.sdf_prog, cache_dir="assets/cache/sdf")
body_font = fonts.get(FontManager.BODY)

# 7. Lighting
lighting = LightingSystem(ctx, renderer.light_prog)

# 8. Camera
camera = Camera(1280, 720)

# 9. Input
Input.bind("quit", pygame.K_ESCAPE)

# 10. Post-processing
fx = PostFX(bloom=0.5, tone_mapping="aces")

# Game loop
running = True
clock = pygame.time.Clock()
while running:
    dt = clock.tick(60) / 1000.0
    events = pygame.event.get()
    Input.update(events)

    for e in events:
        if e.type == pygame.QUIT:
            running = False
    if Input.pressed("quit"):
        running = False

    camera.update(400, 300, 2000, 2000, dt, smoothing=1.0)

    # Render
    renderer.begin_scene()
    batch.begin(player_tex)
    sx, sy = camera.apply(400, 300)
    batch.draw(sx, sy, 64, 64)
    batch.end()

    renderer.begin_lights()
    lighting.clear()
    lighting.add(640, 360, radius=300, color=(1.0, 0.8, 0.5))
    lighting.render()

    renderer.combine(ambient=0.15)
    renderer.post_process(fx)

    renderer.begin_screen_overlay()
    body_font.draw("Score: 100", 20, 20, size=24)
    body_font.flush()

    pygame.display.flip()

# Cleanup
fonts.release()
textures.release_all()
lighting.release()
batch.release()
renderer.release()
pygame.quit()
```

---

## Project Structure

A typical PyLuxel project:

```
my_game/
├── assets/
│   ├── sprites/       # PNG textures
│   ├── fonts/         # TTF font files
│   ├── sfx/           # Sound effects (WAV/OGG)
│   ├── music/         # Music tracks (OGG/MP3)
│   └── maps/          # Tiled JSON maps
├── main.py
└── pyluxel/           # engine (or pip install -e)
```
