from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pyluxel.tilemap.tileset import Tileset
    from pyluxel.tilemap.tile_layer import TileLayer


@dataclass
class MapObject:
    """Un oggetto posizionato sulla mappa (spawn point, trigger, ecc.)."""
    name: str
    type: str
    x: float
    y: float
    width: float = 0.0
    height: float = 0.0
    properties: dict[str, Any] = field(default_factory=dict)
    polygon: list[tuple[float, float]] | None = None
    id: int = 0
    rotation: float = 0.0
    ellipse: bool = False


class TileMap:
    """Container per una mappa completa: tilesets, layers e oggetti.

    Attributi:
        width: larghezza in tile
        height: altezza in tile
        tile_width: larghezza di un tile in pixel
        tile_height: altezza di un tile in pixel
        tilesets: lista di Tileset usati dalla mappa
        layers: lista ordinata di TileLayer (dal piu' basso al piu' alto)
        objects: lista di MapObject (spawn points, trigger zones, ecc.)
    """

    def __init__(self, width: int, height: int,
                 tile_width: int, tile_height: int):
        self.width = width
        self.height = height
        self.tile_width = tile_width
        self.tile_height = tile_height

        self.tilesets: list[Tileset] = []
        self.layers: list[TileLayer] = []
        self.objects: list[MapObject] = []

    @property
    def pixel_width(self) -> int:
        """Larghezza totale della mappa in pixel."""
        return self.width * self.tile_width

    @property
    def pixel_height(self) -> int:
        """Altezza totale della mappa in pixel."""
        return self.height * self.tile_height

    def get_layer(self, name: str) -> TileLayer | None:
        """Trova un layer per nome. None se non esiste."""
        for layer in self.layers:
            if layer.name == name:
                return layer
        return None

    def get_objects(self, type: str | None = None) -> list[MapObject]:
        """Restituisce gli oggetti, opzionalmente filtrati per tipo."""
        if type is None:
            return list(self.objects)
        return [obj for obj in self.objects if obj.type == type]

    def add_layer(self, layer: TileLayer) -> None:
        """Aggiunge un layer alla mappa."""
        self.layers.append(layer)

    def remove_layer(self, name: str) -> bool:
        """Rimuove un layer per nome. Ritorna True se trovato."""
        for i, layer in enumerate(self.layers):
            if layer.name == name:
                self.layers.pop(i)
                return True
        return False

    def add_object(self, obj: MapObject) -> None:
        """Aggiunge un oggetto alla mappa."""
        self.objects.append(obj)

    def remove_object(self, obj: MapObject) -> bool:
        """Rimuove un oggetto dalla mappa. Ritorna True se trovato."""
        try:
            self.objects.remove(obj)
            return True
        except ValueError:
            return False

    def clear_objects(self) -> None:
        """Rimuove tutti gli oggetti dalla mappa."""
        self.objects.clear()

    def get_tileset_for_gid(self, gid: int) -> Tileset | None:
        """Trova il tileset che contiene il global tile ID."""
        for ts in reversed(self.tilesets):
            if ts.contains_gid(gid):
                return ts
        return None

    def get_tile_properties(self, gid: int) -> dict[str, Any]:
        """Restituisce le properties di un tile tramite il tileset corretto."""
        ts = self.get_tileset_for_gid(gid)
        if ts is None:
            return {}
        return ts.get_tile_properties(gid)
