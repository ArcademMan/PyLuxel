# Rendering

Core rendering pipeline: Resolution scaling, HDR framebuffers, sprite batching, textures, camera, and post-processing.

---

## Resolution

Singleton that maps **design space** coordinates to the actual window size. All game logic uses a fixed virtual resolution (default 1280x720).

```python
from pyluxel import R

# Configure at startup
R.init(1280, 720)

# When the window is resized
R.set_resolution(1920, 1080)

# Scale values from design space to screen pixels
button_w = R.s(200)    # -> 300 at 1920x1080 (int)
radius = R.sf(33.5)    # -> 50.25 (float, for precise math)

# Reverse: screen pixels to design space
design_val = R.unscale(300)  # -> 200.0

# Center of design space
x = R.center_x  # 640
y = R.center_y  # 360
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `width` | `int` | Current window width in pixels |
| `height` | `int` | Current window height in pixels |
| `center_x` | `int` | `BASE_WIDTH // 2` |
| `center_y` | `int` | `BASE_HEIGHT // 2` |
| `scale` | `float` | `width / BASE_WIDTH` |
| `BASE_WIDTH` | `int` | Design resolution width (default 1280) |
| `BASE_HEIGHT` | `int` | Design resolution height (default 720) |
| `PRESETS` | `list` | Available resolution presets |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `init(base_w, base_h, presets=None)` | `Resolution` | Configure design resolution |
| `set_resolution(w, h)` | `None` | Update current window resolution |
| `s(value)` | `int` | Scale design value to screen (rounded) |
| `sf(value)` | `float` | Scale design value to screen (precise) |
| `unscale(screen_value)` | `float` | Screen pixels to design space |
| `get_native_resolution()` | `(int, int)` | Native monitor resolution |
| `native_in_presets()` | `bool` | Whether native resolution is in presets |
| `get_base_resolution()` | `(int, int)` | `(BASE_WIDTH, BASE_HEIGHT)` |

### Custom Presets

```python
R.init(1280, 720, presets=[(1280, 720), (1920, 1080), (3840, 2160)])
```

---

## Renderer

HDR multi-pass rendering pipeline: **scene → [shadow casters] → [normal maps] → lights → combine → post-process → screen overlay**.

All FBOs use RGBA16F (half-float) for HDR. Values above 1.0 are preserved and contribute to bloom.

```python
renderer = Renderer(ctx, screen_width, screen_height,
                    design_width=1280, design_height=720,
                    clear_color=(0.06, 0.05, 0.07))
```

### Rendering Pipeline

```python
# 1. Scene (FBO, alpha blending)
renderer.begin_scene()
batch.begin(texture)
batch.draw(x, y, w, h)
batch.end()

# 2. Shadow casters (optional, for 2D shadows)
renderer.begin_shadow_casters()
batch.begin(white_tex)
batch.draw(wall_x, wall_y, wall_w, wall_h)  # occluders
batch.end()

# 3. Normal maps (optional, for per-pixel lighting)
renderer.begin_normal()
batch.begin(normal_map_texture)
batch.draw(x, y, w, h)
batch.end()

# 4. Lights (FBO, additive blending)
renderer.begin_lights()
lighting.clear()
lighting.add(640, 360, radius=300)
lighting.render(time)

# 5. Combine scene * (ambient + lights)
renderer.combine(ambient=0.15, max_exposure=1.5)

# 6. Post-processing -> screen output
renderer.post_process(fx)  # fx is a PostFX object

# 7. Screen overlay (HUD/UI, drawn after post-processing)
renderer.begin_screen_overlay()
font.draw("Score: 100", 10, 10, size=20)
font.flush()
```

### Methods

| Method | Description |
|--------|-------------|
| `begin_scene()` | Start scene rendering (FBO, alpha blending) |
| `begin_shadow_casters()` | Start shadow occluder rendering (optional, for 2D shadows) |
| `begin_normal()` | Start normal map rendering (optional, for lighting) |
| `begin_lights()` | Start light rendering (FBO, additive blending) |
| `combine(ambient, max_exposure)` | Multiply scene by lightmap |
| `post_process(fx)` | Apply PostFX and render to screen |
| `begin_screen_overlay()` | Draw directly on screen (HUD/UI) |
| `blit_to_screen(texture)` | Display a texture fullscreen (no blending) |
| `blit_overlay(texture)` | Display a texture with alpha blending |
| `resize(width, height)` | Update viewport after window resize |
| `resize_design(dw, dh)` | Change design resolution (recreates FBOs) |
| `set_clear_color(r, g, b)` | Set scene background color |
| `screenshot()` | Capture framebuffer as raw RGBA bytes |
| `release()` | Free all GPU resources |

### Shader Programs (Attributes)

| Attribute | Usage |
|-----------|-------|
| `sprite_prog` | SpriteBatch rendering |
| `sdf_prog` | SDF font rendering |
| `light_prog` | LightingSystem rendering |
| `combine_prog` | Scene + lightmap combine |
| `post_prog` | Post-processing effects |
| `bloom_down_prog` | Bloom downsample |
| `bloom_up_prog` | Bloom upsample |

### FBO Textures

| Attribute | Description |
|-----------|-------------|
| `scene_texture` | Scene FBO color attachment (RGBA16F) |
| `light_texture` | Light FBO color attachment (RGBA16F) |
| `combine_texture` | Combined result (RGBA16F) |
| `normal_texture` | Normal map FBO (RGBA8) |
| `occlusion_texture` | Shadow occluder FBO (RGBA8) |
| `shadow_map_texture` | 1D shadow map (360x1, RGBA8) |

---

## SpriteBatch

GPU-batched sprite renderer. Accumulates up to **4096 sprites** per texture, then draws them in a single draw call.

```python
batch = SpriteBatch(ctx, renderer.sprite_prog)

# Draw sprites
batch.begin(player_texture)
batch.draw(100, 200, 64, 64)                    # basic sprite
batch.draw(300, 200, 64, 64, r=1, g=0, b=0)     # red tint
batch.draw(500, 200, 64, 64, a=0.5)             # semi-transparent
batch.draw(700, 200, 64, 64, angle=0.785)        # rotated 45°
batch.end()

# Colored rectangles (use a 1x1 white texture)
batch.begin(white_tex)
batch.draw(0, 0, 200, 50, r=0.2, g=0.2, b=0.3)
batch.end()
```

### draw() Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `x, y` | required | Top-left position (design space) |
| `w, h` | required | Size (design space) |
| `u0, v0` | 0, 0 | UV top-left (for sprite sheets) |
| `u1, v1` | 1, 1 | UV bottom-right |
| `r, g, b` | 1, 1, 1 | Color tint (multiplied with texture) |
| `a` | 1 | Alpha / opacity |
| `angle` | 0 | Rotation in radians (around sprite center) |

### Sprite Sheet UVs

```python
# 256x256 atlas, 32x32 sprites, get sprite at column 2, row 3
col, row = 2, 3
u0 = col * 32 / 256
v0 = row * 32 / 256
u1 = (col + 1) * 32 / 256
v1 = (row + 1) * 32 / 256
batch.draw(x, y, 32, 32, u0=u0, v0=v0, u1=u1, v1=v1)
```

### Methods

| Method | Description |
|--------|-------------|
| `begin(texture)` | Start batch with a texture |
| `draw(...)` | Add a sprite to the batch |
| `flush()` | Send current batch to GPU and draw |
| `end()` | Flush and reset (alias for flush + clear texture) |
| `clear()` | Discard queued sprites without drawing |
| `get_sprite_count()` | Number of sprites queued before flush |
| `release()` | Free GPU resources |

---

## TextureManager

Loads and caches GPU textures from PNG files.

```python
textures = TextureManager(ctx, base_path="assets/sprites")

# Load a texture (cached)
player_tex = textures.load("player")        # loads assets/sprites/player.png
player_tex = textures.load("player.png")    # same thing

# Create from pygame Surface
tex = textures.surface_to_texture(my_surface)

# Create solid color texture (useful for colored quads)
white_tex = textures.create_from_color(1, 1)                      # 1x1 white
red_tex = textures.create_from_color(1, 1, color=(255, 0, 0, 255))

# Hot-reload from disk
textures.reload("player")

# Cache management
textures.is_cached("player")       # True
textures.get_cached_names()        # ["player", "__color_1x1_..."]
textures.release("player")        # release one
textures.release_all()            # release all
```

---

## Camera

2D camera with smooth follow, map edge clamping, and screen shake.

```python
camera = Camera(design_width=1280, design_height=720)

# Each frame: follow a target with smooth interpolation
camera.update(
    target_x=player.x,
    target_y=player.y,
    map_width=map_pixel_width,
    map_height=map_pixel_height,
    dt=dt,
    smoothing=1.0,        # 0 = instant snap, higher = smoother
)

# Convert world coordinates to screen coordinates
screen_x, screen_y = camera.apply(world_x, world_y)

# Convert screen coordinates back to world
world_x, world_y = camera.screen_to_world(screen_x, screen_y)

# Direct snap (no smooth follow)
camera.set_position(x, y)

# Screen shake (resets every frame, call after update)
camera.shake(intensity=5.0)

# Zoom (1.0 = default, >1 = zoom in, <1 = zoom out)
camera.set_zoom(2.0)
zoom = camera.get_zoom()

# Get visible area in world coordinates
left, top, right, bottom = camera.get_bounds()

# --- GPU-accelerated camera (recommended) ---
# Pass camera to begin_scene — all draw calls use world coordinates,
# zoom and offset are applied automatically by the GPU.
renderer.begin_scene(camera)
batch.draw(world_x, world_y, width, height, ...)  # no camera.apply() needed!
# ...
renderer.begin_screen_overlay()  # resets to design space for HUD

# You can also apply/remove camera manually mid-frame:
renderer.apply_camera(camera)
renderer.reset_camera()
```

---

## PostFX

Dataclass for configuring all post-processing effects. Parameters set to 0.0 or `False` have zero GPU cost.

```python
from pyluxel import PostFX

fx = PostFX()

# Modify at runtime
fx.bloom = 0.8
fx.vignette = 2.5
fx.tone_mapping = "aces"       # "aces", "reinhard", or "none"
fx.exposure = 1.2

# Chromatic aberration (0 = off, 0.3-1.0 recommended)
fx.chromatic_aberration = 0.5

# Film grain (0 = off, 0.05-0.2 recommended)
fx.film_grain = 0.1

# CRT effect
fx.set_crt(enabled=True, curvature=0.02, scanline=0.3)

# Color grading LUT (1024x32 strip texture, or None)
fx.set_color_grading_lut(lut_texture)

# God rays
fx.set_god_rays(
    intensity=0.5,    # 0 = off, 0.3-0.8 recommended
    x=0.5,            # UV source X (0-1, 0.5 = center)
    y=0.0,            # UV source Y (0-1, 0.0 = top)
    decay=0.96,       # per-sample decay (0.9-0.99)
    density=0.5,      # ray density (0.3-1.0)
)

# Pixel-perfect scaling (ideal for pixel art)
fx.set_pixel_perfect(True)   # NEAREST: crisp pixels
fx.set_pixel_perfect(False)  # LINEAR: smooth (default)

# Save/restore state
state = fx.get_state()
fx.load_state(state)

# Reset all to defaults
fx.reset()

# Clone for independent config
fx2 = fx.clone()
```

### All PostFX Fields

| Field | Default | Description |
|-------|---------|-------------|
| `vignette` | `2.0` | Radial vignette intensity (0 = off) |
| `bloom` | `0.5` | Dual-kawase bloom intensity (0 = off) |
| `tone_mapping` | `"aces"` | `"aces"`, `"reinhard"`, or `"none"` |
| `exposure` | `1.0` | Pre-tonemapping exposure multiplier |
| `chromatic_aberration` | `0.0` | Edge aberration (0 = off) |
| `film_grain` | `0.0` | Animated film grain (0 = off) |
| `crt` | `False` | Enable CRT effect |
| `crt_curvature` | `0.02` | Barrel curvature amount |
| `crt_scanline` | `0.3` | Scanline intensity |
| `color_grading_lut` | `None` | LUT texture for color grading |
| `god_rays` | `0.0` | God rays intensity (0 = off) |
| `god_rays_x` | `0.5` | God rays source X (UV 0-1) |
| `god_rays_y` | `0.0` | God rays source Y (UV 0-1) |
| `god_rays_decay` | `0.96` | Per-sample decay |
| `god_rays_density` | `0.5` | Ray density |
| `pixel_perfect` | `False` | NEAREST scaling for crisp pixels (scene only, HUD unaffected) |

---

## Shockwave

UV distortion effect that expands outward from a point.

```python
# Via ShockwaveManager (accessed through renderer)
sw = renderer.shockwaves.add(
    x=400, y=300,          # center position (design space)
    max_radius=200.0,      # maximum expansion radius
    thickness=30.0,        # ring thickness
    strength=0.05,         # distortion strength
)

# Each frame
renderer.shockwaves.update(dt)

# Modify a live shockwave
sw.set_position(500, 400)
sw.set_params(max_radius=300, strength=0.08)

# Check state
sw.is_alive()             # False when fully expanded
sw.radius                 # current radius
renderer.shockwaves.get_count()
renderer.shockwaves.is_full()   # max 8 simultaneous

# Remove
renderer.shockwaves.remove(sw)
renderer.shockwaves.clear()
```

---

## HeatHaze

Persistent oscillating distortion zones (heat shimmer, steam, portals).

Unlike shockwaves, heat hazes are persistent and oscillate continuously.

```python
# Add a distortion zone
haze = renderer.heat_hazes.add(
    x=200, y=400,            # top-left position (design space)
    width=100, height=200,   # zone size
    strength=0.003,          # distortion intensity (0.001-0.01)
    speed=3.0,               # oscillation speed
    scale=20.0,              # distortion pattern scale
)

# Modify at runtime
haze.set_position(300, 400)
haze.set_size(150, 250)
haze.set_params(strength=0.005, speed=4.0)

# Management
renderer.heat_hazes.get_count()
renderer.heat_hazes.is_full()   # max 4 simultaneous
renderer.heat_hazes.remove(haze)
renderer.heat_hazes.clear()
```
