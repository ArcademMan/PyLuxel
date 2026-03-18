"""
pyluxel -- Engine 2D riutilizzabile basato su pygame-ce + ModernGL.

Installa con pip:
    pip install -e path/to/pyluxel

Oppure copia la cartella nella root del progetto e importa:
    from pyluxel import Renderer, SpriteBatch, Camera, R, FontManager, ...
"""

__version__ = "0.2.0"

# Core rendering
from pyluxel.core.renderer import Renderer
from pyluxel.core.texture_manager import TextureManager
from pyluxel.core.camera import Camera
from pyluxel.core.sprite_batch import SpriteBatch
from pyluxel.core.resolution import Resolution
from pyluxel.core.paths import base_path, user_data_dir
from pyluxel.core.pak import asset_open, asset_exists, init_pak, has_pak
from pyluxel.core.scene import Scene, SceneManager
from pyluxel.core.timer import Timer
from pyluxel.core.event_bus import EventBus, Events

# Physics
from pyluxel.physics import (aabb_vs_aabb, aabb_vs_point, aabb_vs_circle,
                              aabb_overlap, circle_vs_circle, circle_vs_point,
                              ray_vs_aabb, collides_aabb_list)

# Post-processing
from pyluxel.core.post_fx import (PostFX, Shockwave, ShockwaveManager,
                                  HeatHaze, HeatHazeManager)

# Transitions
from pyluxel.effects.transition import Transition, TransitionMode

# Effects
from pyluxel.effects.lighting import Light, LightingSystem, FalloffMode
from pyluxel.effects.fog import FogLayer
from pyluxel.effects.particles import (
    ParticleSystem, ParticlePreset,
    SHAPE_CIRCLE, SHAPE_SQUARE, SHAPE_SPARK, SHAPE_RING,
    SHAPE_STAR, SHAPE_DIAMOND, SHAPE_TRIANGLE, SHAPE_SOFT_DOT,
    FIRE, SMOKE, EXPLOSION, SPARK_SHOWER, RAIN,
    SNOW, MAGIC, BLOOD, DUST, STEAM,
)

# Text
from pyluxel.text.sdf_font import SDFFont, SDFFontCache
from pyluxel.text.bitmap_font import BitmapFont, FontCache
from pyluxel.text.fonts import FontManager

# Tilemap
from pyluxel.tilemap.tileset import Tileset
from pyluxel.tilemap.tile_layer import TileLayer
from pyluxel.tilemap.tile_map import TileMap, MapObject
from pyluxel.tilemap.loader import load_map
from pyluxel.tilemap.parallax import ParallaxLayer, ParallaxBackground

# UI
from pyluxel.ui import (Theme, Button, Toggle, Slider, LineEdit, Dropdown,
                       RoundedRectRenderer, FocusManager, VBox, HBox, render_widgets,
                       GlyphText, load_ps_glyphs)

# Animation
from pyluxel.animation import (
    Bone, Skeleton, Pose, Animation, LoopMode, Animator,
    BoneVisual, EyeConfig, StickmanConfig, Stickman,
    AnimStateMachine,
    create_default_skeleton, create_default_config, create_default_stickman,
    load_preset,
    IDLE, WALK, RUN, JUMP, FALL, LANDING, ATTACK,
    ModelData, save_model, load_model, export_animation, build_animation,
    create_empty_model, model_from_defaults,
)

# Audio
from pyluxel.audio import SoundManager, Sound

# Input
from pyluxel.input import InputManager, InputDevice, Input, Mouse, Pad, Stick

# Debug
from pyluxel.debug import cprint, CPrint, Cprint, GPUStats

# Networking (optional -- steamworks non richiesto)
from pyluxel.net import Net, NetworkManager, NetNode, Peer, rpc, RPCTarget, host_only, synced

# App bootstrap
from pyluxel.app import App

# Singleton alias
R = Resolution()

__all__ = [
    # Core
    "Renderer",
    "TextureManager",
    "Camera",
    "SpriteBatch",
    "Resolution",
    "R",
    "base_path",
    "user_data_dir",
    "asset_open",
    "asset_exists",
    "init_pak",
    "has_pak",
    "Scene",
    "SceneManager",
    "Timer",
    "EventBus",
    "Events",
    # Physics
    "aabb_vs_aabb",
    "aabb_vs_point",
    "aabb_vs_circle",
    "aabb_overlap",
    "circle_vs_circle",
    "circle_vs_point",
    "ray_vs_aabb",
    "collides_aabb_list",
    # Post-processing
    "PostFX",
    "Shockwave",
    "ShockwaveManager",
    "HeatHaze",
    "HeatHazeManager",
    # Transitions
    "Transition",
    "TransitionMode",
    # Effects
    "Light",
    "LightingSystem",
    "FalloffMode",
    "FogLayer",
    "ParticleSystem",
    "ParticlePreset",
    "SHAPE_CIRCLE", "SHAPE_SQUARE", "SHAPE_SPARK", "SHAPE_RING",
    "SHAPE_STAR", "SHAPE_DIAMOND", "SHAPE_TRIANGLE", "SHAPE_SOFT_DOT",
    "FIRE", "SMOKE", "EXPLOSION", "SPARK_SHOWER", "RAIN",
    "SNOW", "MAGIC", "BLOOD", "DUST", "STEAM",
    # Text
    "SDFFont",
    "SDFFontCache",
    "BitmapFont",
    "FontCache",
    "FontManager",
    # Tilemap
    "Tileset",
    "TileLayer",
    "TileMap",
    "MapObject",
    "load_map",
    "ParallaxLayer",
    "ParallaxBackground",
    # UI
    "Theme",
    "Button",
    "Toggle",
    "Slider",
    "LineEdit",
    "Dropdown",
    "RoundedRectRenderer",
    "FocusManager",
    "VBox",
    "HBox",
    "render_widgets",
    "GlyphText",
    "load_ps_glyphs",
    # Animation
    "Bone",
    "Skeleton",
    "Pose",
    "Animation",
    "LoopMode",
    "Animator",
    "BoneVisual",
    "EyeConfig",
    "StickmanConfig",
    "Stickman",
    "AnimStateMachine",
    "create_default_skeleton",
    "create_default_config",
    "create_default_stickman",
    "load_preset",
    "IDLE",
    "WALK",
    "RUN",
    "JUMP",
    "ATTACK",
    "ModelData",
    "save_model",
    "load_model",
    "export_animation",
    "build_animation",
    "create_empty_model",
    "model_from_defaults",
    # Audio
    "SoundManager",
    "Sound",
    # Input
    "InputManager",
    "Input",
    "Mouse",
    "Pad",
    "Stick",
    # Debug
    "cprint",
    "CPrint",
    "Cprint",
    "GPUStats",
    # Networking
    "Net",
    "NetworkManager",
    "NetNode",
    "Peer",
    "rpc",
    "RPCTarget",
    "host_only",
    "synced",
    # App
    "App",
]
