# App

Bootstrap class that creates a complete PyLuxel application in one line. Handles window creation, OpenGL context, renderer, sprite batch, lighting, input, audio, and the game loop.

---

## Two Patterns

### Decorator Pattern (quick prototyping)

```python
from pyluxel import App, Input
import pygame

app = App(1280, 720, "My Game")
Input.bind("quit", pygame.K_ESCAPE)

@app.on_update
def update(dt):
    if Input.pressed("quit"):
        app.quit()

@app.on_draw
def draw():
    app.draw_rect(100, 100, 50, 50, r=1, g=0, b=0)

app.run()
```

### Subclass Pattern (production)

```python
from pyluxel import App, Input
import pygame

class MyGame(App):
    def setup(self):
        Input.bind("quit", pygame.K_ESCAPE)
        self.player_x = 100

    def update(self, dt):
        if Input.pressed("quit"):
            self.quit()
        self.player_x += 100 * dt

    def draw(self):
        self.draw_rect(self.player_x, 100, 32, 32, r=0, g=1, b=0)

MyGame(1280, 720, "My Game").run()
```

---

## Constructor

```python
App(
    width=1280,                 # window width
    height=720,                 # window height
    title="PyLuxel",            # window title
    design_width=None,          # design resolution width (defaults to width)
    design_height=None,         # design resolution height (defaults to height)
    fps=60,                     # frame rate cap
    vsync=False,                # vertical sync
    resizable=False,            # resizable window
    centered=False,             # center window on screen
    clear_color=(0.05, 0.04, 0.07),  # background clear color (RGB)
)
```

The constructor initializes everything:
- pygame + OpenGL window
- `ModernGL` context (`app.ctx`)
- `Resolution` singleton (design space = window size by default)
- `Renderer` with full HDR FBO pipeline (`app.renderer`)
- `SpriteBatch` (`app.batch`)
- `LightingSystem` (`app.lighting`)
- `TextureManager` (`app.textures`)
- 1x1 white texture (`app.white_tex`)
- `FontManager` + `SDFFontCache` for text
- `Input` and `Sound` singletons

---

## Lifecycle Hooks

Override these methods in a subclass, or register them with decorators.

| Hook | Decorator | When |
|------|-----------|------|
| `setup()` | — | Once before the game loop |
| `update(dt)` | `@app.on_update` | Every frame (dt in seconds) |
| `draw()` | `@app.on_draw` | Scene rendering (scene FBO active) |
| `draw_lights()` | `@app.on_draw_lights` | Add dynamic lights (light FBO active) |
| `shadow_casters()` | `@app.on_shadow_casters` | Draw shadow occluders (occlusion FBO active) |
| `draw_overlay()` | `@app.on_draw_overlay` | HUD/UI after post-processing |
| `handle_event(event)` | `@app.on_event` | Raw pygame events |
| `handle_resize(w, h)` | `@app.on_resize` | Window resized |

### Rendering Pipeline Order

Each frame, App executes:

1. `update(dt)` — game logic
2. `renderer.begin_scene()` → `draw()` — scene rendering
3. `renderer.begin_shadow_casters()` → `shadow_casters()` — shadow occluders (if any shadow light exists)
4. `renderer.begin_lights()` → persistent lights + `draw_lights()` — lighting
5. `renderer.combine(ambient)` — combine scene + lights
6. `renderer.post_process(fx)` — bloom, tone mapping, vignette, etc.
7. `renderer.begin_screen_overlay()` — transition overlay → `draw_overlay()` — HUD

---

## Properties

| Property | Type | Description |
|----------|------|-------------|
| `width` | `int` | Current window width |
| `height` | `int` | Current window height |
| `dt` | `float` | Delta time (seconds, clamped to 0.05 max) |
| `time` | `float` | Total elapsed time (seconds) |
| `current_fps` | `float` | Current FPS from clock |
| `fps_cap` | `int` | FPS cap (read/write) |
| `is_fullscreen` | `bool` | True if fullscreen |
| `mouse_x` | `float` | Mouse X in design space |
| `mouse_y` | `float` | Mouse Y in design space |
| `show_fps` | `bool` | Show FPS overlay |
| `show_stats` | `bool` | Show GPU stats overlay (VRAM, draw calls, sprites) |

---

## Built-in Objects

Available after construction:

| Attribute | Type | Description |
|-----------|------|-------------|
| `ctx` | `moderngl.Context` | OpenGL context |
| `renderer` | `Renderer` | HDR FBO rendering pipeline |
| `batch` | `SpriteBatch` | GPU sprite batcher |
| `lighting` | `LightingSystem` | 2D lighting system |
| `textures` | `TextureManager` | Texture loader/cache |
| `white_tex` | `moderngl.Texture` | 1x1 white texture |
| `fx` | `PostFX` | Post-processing config |
| `input` | `InputManager` | Alias for `Input` singleton |
| `sound` | `SoundManager` | Alias for `Sound` singleton |

---

## Drawing Shortcuts

### Sprites

```python
# Auto-begin batch with the given texture (or white_tex if None)
app.draw_sprite(x, y, w, h, texture=tex, r=1, g=1, b=1, a=1, angle=0)

# Colored rectangle (fast batch for angle=0, GPU SDF for rotated)
app.draw_rect(x, y, w, h, r=1, g=0, b=0, a=1, angle=0)

# Manual batch control
app.begin(texture)      # begin batch (auto-flushes previous)
app.end()               # flush and draw
```

### Shapes (GPU SDF)

All shapes are rendered with per-pixel signed distance fields. Anti-aliased at any scale and rotation.

```python
# Circle (x, y = center)
app.draw_circle(x, y, radius, r=1, g=1, b=1, a=1)

# Triangle (isosceles, tip pointing up, x, y = center)
app.draw_triangle(x, y, w, h, r=1, g=1, b=1, a=1, angle=0)

# Regular polygon (x, y = center)
app.draw_polygon(x, y, radius, sides=6, r=1, g=1, b=1, a=1, angle=0)

# Star (x, y = center, inner_ratio = inner/outer radius)
app.draw_star(x, y, radius, points=5, inner_ratio=0.4, r=1, g=1, b=1, a=1, angle=0)

# Capsule (rounded rectangle, x, y = center)
app.draw_capsule(x, y, w, h, r=1, g=1, b=1, a=1, angle=0)

# Line (from point to point, rounded caps)
app.draw_line(x1, y1, x2, y2, r=1, g=1, b=1, a=1, width=2)
```

### Text

```python
# Draw text (SDF, auto-flushed at end of frame)
app.draw_text("Hello", x, y, size=24, font="body", r=1, g=1, b=1, a=1,
              align_x="left", align_y="top")

# Measure without drawing
w, h = app.measure_text("Hello", size=24, font="body")

# Configure custom fonts
app.init_fonts("assets/fonts", {
    "body": "Inter-Regular.ttf",
    "title": "Inter-Bold.ttf",
}, cache_dir="assets/cache/sdf")

# Get the SDFFont object
font = app.get_font("body")
```

---

## Lights

Persistent lights are managed by the App and automatically rendered each frame.

```python
# Add a persistent light
light = app.add_light(
    x=400, y=300, radius=200,
    color=(1.0, 0.8, 0.5), intensity=1.2,
    falloff=FalloffMode.QUADRATIC,
    is_spotlight=False,
    flicker_speed=8.0, flicker_amount=0.2, flicker_style="candle",
    z=70.0,
    cast_shadows=False,       # True to project 2D shadows (max 64)
    shadow_softness=0.02,     # penumbra size (0.01=hard, 0.1=soft)
)

# Move it at runtime
light.x = player_x
light.y = player_y

# Remove
app.remove_light(light)
app.clear_lights()
app.get_lights()         # list of Light
app.light_count          # int
```

For dynamic lights (added/removed each frame), use `draw_lights()`:

```python
def draw_lights(self):
    self.lighting.add(enemy_x, enemy_y, radius=100, color=(1, 0, 0))
```

---

## Shadows

Lights with `cast_shadows=True` project dynamic 2D shadows from occluder geometry. Up to 64 shadow-casting lights are supported (batched via shadow map atlas).

```python
# Add a shadow-casting light
light = app.add_light(400, 300, radius=250,
                      color=(1.0, 0.9, 0.7), intensity=1.5,
                      cast_shadows=True, shadow_softness=0.03)

# Draw occluders (white = blocks light)
@app.on_shadow_casters
def shadow_casters():
    app.draw_rect(wall_x, wall_y, wall_w, wall_h, r=1, g=1, b=1)
```

Subclass pattern:

```python
class MyGame(App):
    def setup(self):
        self.light = self.add_light(400, 300, radius=250,
                                    cast_shadows=True)
        self.walls = [(300, 200, 40, 250), (600, 150, 200, 30)]

    def shadow_casters(self):
        for wx, wy, ww, wh in self.walls:
            self.draw_rect(wx, wy, ww, wh, r=1, g=1, b=1)
```

The `shadow_casters()` hook is only called when at least one light has `cast_shadows=True`. Toggle at runtime:

```python
light.cast_shadows = False             # disable
light.set_shadow_casting(True, 0.05)   # enable with custom softness
```

---

## Post-Processing

```python
# Direct access to PostFX dataclass
app.fx.bloom = 0.8
app.fx.vignette = 0.3
app.fx.tone_mapping = "aces"      # "aces", "reinhard", or "none"
app.fx.exposure = 1.0
app.fx.god_rays = 0.5

# Convenience method
app.set_post_process(bloom=0.8, vignette=0.3, tone_mapping="aces", exposure=1.0)

# God rays convenience
app.set_god_rays(intensity=0.5, x=0.5, y=0.0, decay=0.96, density=0.5)

# Ambient light level (used in combine pass)
app.set_post_process(ambient=0.15)

# Pixel-perfect scaling (scene only, HUD unaffected)
app.fx.set_pixel_perfect(True)   # NEAREST: crisp pixels (pixel art)
app.fx.set_pixel_perfect(False)  # LINEAR: smooth scaling (default)
```

---

## Shockwaves & Heat Haze

```python
# UV distortion shockwave (one-shot)
app.add_shockwave(x=400, y=300, max_radius=200, thickness=30, strength=0.05)

# Persistent heat haze zone
haze = app.add_heat_haze(x=100, y=400, width=200, height=100,
                         strength=0.003, speed=3.0, scale=20.0)
app.remove_heat_haze(haze)
app.clear_heat_hazes()
```

---

## Transitions

```python
from pyluxel import TransitionMode

# Start a fade-out
app.start_transition(
    mode=TransitionMode.FADE,       # FADE, DISSOLVE, WIPE_LEFT, WIPE_DOWN, DIAMOND
    duration=1.0,
    color=(0.0, 0.0, 0.0),
    reverse=False,                   # False=fade out, True=fade in
    on_complete=lambda: print("done"),
)

# Query state
app.transition_active      # True if running
app.transition_done        # True if finished
app.transition_progress    # 0.0 → 1.0

app.stop_transition()
```

---

## Window Control

```python
app.quit()                                # stop game loop
app.toggle_fullscreen()                   # toggle fullscreen
app.set_fullscreen(True)                  # explicit fullscreen
app.set_resolution(1920, 1080)            # change window size (windowed only)
app.set_vsync(True)                       # toggle VSync
app.set_window_title("New Title")
app.get_window_title()                    # "New Title"
app.get_design_resolution()               # (1280, 720)
app.get_window_resolution()               # (1920, 1080)
app.screenshot("screenshot.png")          # save PNG

# Debug overlays
app.ShowFPS(val=True)          # show FPS counter (pass False to hide)
app.ShowStats(val=True)        # show FPS + VRAM + draw calls (pass False to hide)
```

---

## Complete Example

```python
from pyluxel import App, Input, Sound, FalloffMode, TransitionMode, Mouse, Pad
import pygame

class MyGame(App):
    def setup(self):
        Input.bind("quit", pygame.K_ESCAPE)
        Input.bind("shoot", Mouse.LEFT, Pad.RT)

        self.fx.bloom = 0.5
        self.fx.vignette = 0.2
        self.fx.tone_mapping = "aces"

        self.add_light(640, 360, radius=300, color=(1, 0.9, 0.7),
                       flicker_speed=6, flicker_amount=0.15,
                       flicker_style="candle")

        self.ShowFPS()

    def update(self, dt):
        if Input.pressed("quit"):
            self.quit()
        if Input.pressed("shoot"):
            self.add_shockwave(self.mouse_x, self.mouse_y)

    def draw(self):
        self.draw_rect(600, 320, 80, 80, r=0.2, g=0.6, b=1.0)
        self.draw_circle(400, 400, 30, r=1, g=0.3, b=0.1)
        self.draw_star(800, 300, 40, points=5, r=1, g=0.9, b=0.2)

    def draw_overlay(self):
        self.draw_text("Click to shockwave!", 640, 50, size=28,
                       align_x="center")

MyGame(1280, 720, "PyLuxel Demo", centered=True).run()
```
