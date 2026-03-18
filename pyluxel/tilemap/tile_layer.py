from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyluxel.tilemap.tileset import Tileset
    from pyluxel.core.sprite_batch import SpriteBatch
    from pyluxel.core.camera import Camera


class TileLayer:
    """Un singolo layer di tile: griglia 2D di tile ID.

    tile_id 0 = cella vuota (non disegnata).
    tile_id > 0 = global ID che mappa a un Tileset.
    """

    def __init__(self, name: str, width: int, height: int,
                 tile_width: int, tile_height: int,
                 data: list[list[int]] | None = None):
        self.name = name
        self.width = width
        self.height = height
        self.tile_width = tile_width
        self.tile_height = tile_height
        self.visible = True
        self.opacity = 1.0

        # Griglia: data[row][col], 0 = vuoto
        if data is not None:
            self.data = data
        else:
            self.data = [[0] * width for _ in range(height)]

    def get(self, tx: int, ty: int) -> int:
        """Ottieni il tile ID alla posizione griglia (tx, ty). 0 se fuori range."""
        if 0 <= tx < self.width and 0 <= ty < self.height:
            return self.data[ty][tx]
        return 0

    def set(self, tx: int, ty: int, tile_id: int) -> None:
        """Imposta il tile ID alla posizione griglia."""
        if 0 <= tx < self.width and 0 <= ty < self.height:
            self.data[ty][tx] = tile_id

    def clear(self) -> None:
        """Resetta tutte le celle a 0 (vuote)."""
        for row in self.data:
            for i in range(len(row)):
                row[i] = 0

    def fill(self, tile_id: int) -> None:
        """Riempie tutte le celle con lo stesso tile ID."""
        for row in self.data:
            for i in range(len(row)):
                row[i] = tile_id

    def fill_rect(self, tx: int, ty: int, w: int, h: int, tile_id: int) -> None:
        """Riempie un'area rettangolare con un tile ID."""
        for row in range(max(0, ty), min(self.height, ty + h)):
            for col in range(max(0, tx), min(self.width, tx + w)):
                self.data[row][col] = tile_id

    def is_solid(self, tx: int, ty: int) -> bool:
        """True se la cella non e' vuota (tile_id != 0). Usare per collision layer."""
        return self.get(tx, ty) != 0

    def world_to_tile(self, wx: float, wy: float) -> tuple[int, int]:
        """Converte coordinate mondo in coordinate griglia."""
        return int(wx // self.tile_width), int(wy // self.tile_height)

    def tile_to_world(self, tx: int, ty: int) -> tuple[float, float]:
        """Converte coordinate griglia in coordinate mondo (angolo top-left del tile)."""
        return float(tx * self.tile_width), float(ty * self.tile_height)

    def render(self, batch: SpriteBatch, tileset: Tileset,
               camera: Camera, screen_w: float, screen_h: float) -> None:
        """Renderizza i tile visibili nel batch. Applica camera culling.

        Args:
            batch: SpriteBatch gia' iniziato con begin(tileset.texture)
            tileset: il Tileset da cui prendere le UV
            camera: camera 2D per offset e culling
            screen_w: larghezza viewport in design pixels
            screen_h: altezza viewport in design pixels
        """
        if not self.visible:
            return

        tw = self.tile_width
        th = self.tile_height
        a = self.opacity

        # Calcola range di tile visibili (camera culling)
        min_tx = max(0, int(camera.x // tw))
        min_ty = max(0, int(camera.y // th))
        max_tx = min(self.width, int((camera.x + screen_w) // tw) + 2)
        max_ty = min(self.height, int((camera.y + screen_h) // th) + 2)

        for ty in range(min_ty, max_ty):
            row = self.data[ty]
            for tx in range(min_tx, max_tx):
                gid = row[tx]
                if gid == 0:
                    continue

                u0, v0, u1, v1 = tileset.get_uvs(gid)
                sx, sy = camera.apply(tx * tw, ty * th)

                batch.draw(sx, sy, tw, th,
                           u0=u0, v0=v0, u1=u1, v1=v1,
                           a=a)
