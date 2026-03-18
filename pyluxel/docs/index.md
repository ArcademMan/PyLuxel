# PyLuxel Engine

A 2D game engine built on **pygame-ce** + **ModernGL** with HDR rendering, lighting, post-processing, and more.

## Installation

```bash
pip install -e path/to/pyluxel
```

Or copy the `pyluxel/` folder into your project root.

## Quick Import

```python
from pyluxel import (
    # Core rendering
    App, R, Resolution, Renderer, SpriteBatch, TextureManager, Camera,

    # Post-processing & effects
    PostFX, Shockwave, ShockwaveManager, FalloffMode,
    HeatHaze, HeatHazeManager, Transition, TransitionMode,

    # Lighting, fog, particles
    Light, LightingSystem, FogLayer, ParticleSystem, ParticlePreset,
    SHAPE_CIRCLE, SHAPE_SQUARE, SHAPE_SPARK, SHAPE_RING,
    SHAPE_STAR, SHAPE_DIAMOND, SHAPE_TRIANGLE, SHAPE_SOFT_DOT,
    FIRE, SMOKE, EXPLOSION, SPARK_SHOWER, RAIN,
    SNOW, MAGIC, BLOOD, DUST, STEAM,

    # Text
    SDFFont, SDFFontCache, BitmapFont, FontCache, FontManager,

    # Tilemap & parallax
    Tileset, TileLayer, TileMap, MapObject, load_map,
    ParallaxLayer, ParallaxBackground,

    # UI widgets
    Theme, Button, Toggle, Slider, LineEdit, Dropdown,
    RoundedRectRenderer, FocusManager, VBox, HBox, render_widgets,

    # Skeletal animation
    Bone, Skeleton, Pose, Animation, LoopMode, Animator,
    BoneVisual, EyeConfig, StickmanConfig, Stickman,
    AnimStateMachine,
    create_default_skeleton, create_default_config, create_default_stickman,
    IDLE, WALK, RUN, JUMP, FALL, LANDING, ATTACK,
    ModelData, save_model, load_model, export_animation, build_animation,
    create_empty_model, model_from_defaults,

    # Events
    EventBus, Events,

    # Networking
    Net, NetworkManager, NetNode, Peer, rpc, RPCTarget, host_only, synced,

    # Audio & input
    SoundManager, Sound,
    Input, InputManager, Mouse, Pad, Stick,

    # Asset pak & utilities
    asset_open, asset_exists, init_pak, has_pak,
    cprint, base_path, user_data_dir,
)
```

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](getting-started.md) | Minimal setup, first window, App bootstrap |
| [Rendering](rendering.md) | Resolution, Renderer, SpriteBatch, TextureManager, Camera, PostFX, Shockwave, HeatHaze |
| [Effects](effects.md) | LightingSystem, FogLayer, ParticleSystem, Transition |
| [Text](text.md) | SDFFont, BitmapFont, FontManager |
| [UI](ui.md) | Theme, Button, Toggle, Slider, LineEdit, Dropdown, layouts |
| [Animation](animation.md) | Bone, Skeleton, Animator, Stickman, state machine, presets |
| [World](world.md) | Tileset, TileLayer, TileMap, Parallax, map loading |
| [Networking](networking.md) | Net singleton, P2P host/client, synced(), @rpc, event bus, clock sync, lobby, Steam/UDP |
| [Events](events.md) | EventBus pub/sub, global Events singleton |
| [Audio & Input](audio-input.md) | SoundManager, InputManager, gamepad support |
| [App](app.md) | App bootstrap class, shapes, text shortcuts |
| [Asset PAK](pak.md) | Impacchettamento asset, CLI `pyluxel pak`, protezione file |
| [API Reference](api-reference.md) | Quick cheatsheet with all signatures |

## Key Concepts

- **Design space**: All coordinates use a virtual resolution (default 1280x720). The `Resolution` singleton scales everything to the actual window size.
- **HDR pipeline**: Framebuffers use RGBA16F. Values above 1.0 are preserved and contribute to bloom.
- **Rendering order**: `begin_scene()` → `[begin_normal()]` → `begin_lights()` → `combine()` → `post_process(fx)` → `begin_screen_overlay()`
- **Singletons**: `R` (Resolution), `Input`, `Sound`, `Net`, `Events`, `FontManager`, `SDFFontCache` are pre-initialized singletons.
- **Action-based input**: Bind logical actions to physical keys/buttons, then query with `pressed()` / `held()` / `released()`.
