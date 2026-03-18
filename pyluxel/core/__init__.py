"""pyluxel.core -- Fondamentali del rendering: Renderer, SpriteBatch, Camera, TextureManager, Resolution, Scene, Timer."""

from pyluxel.core.renderer import Renderer
from pyluxel.core.sprite_batch import SpriteBatch
from pyluxel.core.texture_manager import TextureManager
from pyluxel.core.camera import Camera
from pyluxel.core.resolution import Resolution
from pyluxel.core.scene import Scene, SceneManager
from pyluxel.core.timer import Timer
from pyluxel.core.event_bus import EventBus, Events

R = Resolution()

__all__ = [
    "Renderer",
    "SpriteBatch",
    "TextureManager",
    "Camera",
    "Resolution",
    "R",
    "Scene",
    "SceneManager",
    "Timer",
    "EventBus",
    "Events",
]
