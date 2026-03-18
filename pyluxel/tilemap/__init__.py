"""pyluxel.tilemap -- Mappe tile-based, loader JSON e parallax backgrounds."""

from pyluxel.tilemap.tileset import Tileset
from pyluxel.tilemap.tile_layer import TileLayer
from pyluxel.tilemap.tile_map import TileMap, MapObject
from pyluxel.tilemap.loader import load_map
from pyluxel.tilemap.parallax import ParallaxLayer, ParallaxBackground

__all__ = [
    "Tileset",
    "TileLayer",
    "TileMap",
    "MapObject",
    "load_map",
    "ParallaxLayer",
    "ParallaxBackground",
]
