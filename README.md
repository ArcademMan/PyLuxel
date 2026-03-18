<p align="center">
  <img src="https://raw.githubusercontent.com/ArcademMan/PyLuxel/main/PyLuxel.png" alt="PyLuxel" width="400">
</p>

<h1 align="center">PyLuxel</h1>

<p align="center">
  <b>GPU-accelerated 2D game engine for Python</b><br>
  Built on <a href="https://github.com/pygame-community/pygame-ce">pygame-ce</a> + <a href="https://github.com/moderngl/moderngl">ModernGL</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/version-0.2.0-orange.svg" alt="Version">
</p>

---

## What is PyLuxel?

PyLuxel is a 2D game engine that brings **GPU rendering, HDR lighting, and modern post-processing** to Python game development. It wraps pygame-ce for windowing/input and ModernGL for OpenGL rendering, giving you a powerful yet Pythonic API to build 2D games with visual effects that go way beyond what vanilla pygame can do.

---

## Features

### Rendering
- **HDR Pipeline** with RGBA16F framebuffers — values above 1.0 are preserved for bloom
- **SpriteBatch** with GPU instancing for fast texture rendering
- **Design-space coordinates** — work in virtual resolution (e.g. 1280x720), the engine scales to any window size
- **Camera** with smooth follow, zoom, and screen shake

### Lighting & Shading
- **Dynamic lighting system** supporting up to 256 lights per frame
- **Point lights** and **spotlights** with configurable direction, angle, and inner cone
- **Falloff modes**: linear, quadratic, cubic
- **Flickering**: smooth, harsh, candle styles
- **Normal mapping** — render normal map textures and lights compute per-pixel dot(N, L)
- **Ambient + light combine pass** with customizable ambient color

### Post-Processing
- **Dual-Kawase Bloom** (5 mip levels, adjustable intensity)
- **Tone mapping**: ACES, Reinhard, or none
- **God rays** — radial blur from a light source position
- **Heat haze** — persistent oscillating UV distortion zones
- **Shockwaves** — expanding UV distortion rings
- **Fog** — procedural fog layer with height falloff and movement
- **Scene transitions**: fade, dissolve, wipe, diamond

### Text
- **SDF Fonts** — scalable signed-distance-field text, cached atlas generation
- **Bitmap Fonts** — per-size rasterized atlas, pixel-perfect
- **FontManager** singleton for centralized font management

### UI
- **Theme system** with full color/style customization
- **Widgets**: Button, Toggle, Slider, LineEdit, Dropdown
- **Layout**: VBox, HBox containers with auto-spacing
- **Focus system** with keyboard/gamepad navigation
- **GlyphText** — inline icon + text rendering

### Tilemap & World
- **Tiled JSON** map loader (layers, objects, properties)
- **TileLayer** rendering with GPU batching
- **Parallax backgrounds** with multi-layer scrolling

### Animation
- **Skeletal animation** — Bone/Skeleton hierarchy with FK
- **Keyframe system** — Pose, Animation, Animator with loop modes
- **Stickman** — procedural character rendering from skeleton
- **Animation presets**: idle, walk, run, jump, attack
- **Model I/O** — save/load `.model.json` files
- **State machine** for animation blending and transitions

### Networking
- **P2P architecture** — host/client model, no dedicated server needed
- **Dual transport**: raw UDP or Steam Networking Sockets
- **`synced()` descriptor** — automatic state synchronization across peers
- **`@rpc` decorator** — remote procedure calls with target selection (all, host, specific peer)
- **Event bus** — `Net.emit()` / `Net.on_event()` for custom network events
- **Clock synchronization** with `Net.net_time` for consistent timestamps
- **Lobby system** with shareable lobby codes
- **Reliable & unreliable channels**

### Audio
- **SoundManager** with SFX caching and music streaming
- **Spatial 2D audio** — sounds attenuate based on distance from listener

### Input
- **Action-based input** — bind logical actions to keyboard, mouse, and gamepad
- **Query style**: `pressed()`, `held()`, `released()`, `axis()`
- **Gamepad support** with deadzone and stick queries

### Utilities
- **Asset PAK** system — bundle assets into a single encrypted file
- **CLI tool** — `pyluxel pak <directory>` to package assets
- **cprint** — colored console logger for debug output
- **EventBus** — global pub/sub event system

---

## Installation

```bash
pip install pyluxel
```

Or install from source:

```bash
git clone https://github.com/ArcademMan/PyLuxel.git
cd PyLuxel
pip install -e .
```

### Requirements

- Python 3.10+
- pygame-ce >= 2.4.0
- ModernGL >= 5.8.0
- NumPy >= 1.24.0

---

## Quick Start

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
    app.draw_text("Hello PyLuxel!", 640, 360, size=32, align_x="center")

app.run()
```

### With Lighting

```python
from pyluxel import App, Light, Input
import pygame

app = App(1280, 720, "Lights Demo")

Input.bind("quit", pygame.K_ESCAPE)

@app.on_update
def update(dt):
    if Input.pressed("quit"):
        app.quit()

@app.on_draw
def draw():
    app.draw_rect(400, 300, 200, 200, r=0.2, g=0.2, b=0.3)

    app.lighting.clear()
    app.lighting.add(640, 360, radius=400, color=(1.0, 0.8, 0.5))
    app.lighting.add(*Input.mouse_pos(), radius=200, color=(0.3, 0.5, 1.0))

app.fx.bloom = 0.6
app.fx.tone_mapping = "aces"
app.run()
```

---

## Documentation

Full documentation is available in the [`pyluxel/docs/`](pyluxel/docs/) directory:

| Document | Description |
|----------|-------------|
| [Getting Started](pyluxel/docs/getting-started.md) | Minimal setup, first window, App bootstrap |
| [Rendering](pyluxel/docs/rendering.md) | Resolution, Renderer, SpriteBatch, Camera, PostFX |
| [Effects](pyluxel/docs/effects.md) | LightingSystem, FogLayer, ParticleSystem, Transitions |
| [Text](pyluxel/docs/text.md) | SDFFont, BitmapFont, FontManager |
| [UI](pyluxel/docs/ui.md) | Theme, widgets, layouts, focus management |
| [Animation](pyluxel/docs/animation.md) | Skeletal animation, Stickman, state machine |
| [World](pyluxel/docs/world.md) | Tilemap, parallax, map loading |
| [Networking](pyluxel/docs/networking.md) | P2P, synced state, RPC, lobbies, Steam transport |
| [Events](pyluxel/docs/events.md) | EventBus, global pub/sub |
| [Audio & Input](pyluxel/docs/audio-input.md) | SoundManager, InputManager, gamepad |
| [App](pyluxel/docs/app.md) | App bootstrap, shapes, text shortcuts |
| [Asset PAK](pyluxel/docs/pak.md) | Asset packaging and CLI |
| [API Reference](pyluxel/docs/api-reference.md) | Full API cheatsheet |

---

## Project Structure

```
my_game/
├── assets/
│   ├── sprites/       # PNG textures
│   ├── fonts/         # TTF font files
│   ├── sfx/           # Sound effects (WAV/OGG)
│   ├── music/         # Music tracks (OGG/MP3)
│   └── maps/          # Tiled JSON maps
├── main.py
└── ...
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
