from typing import Any

import moderngl


class Tileset:
    """Tileset: uno spritesheet suddiviso in tile di dimensione fissa.

    Dato un tile_id (0-based, riga per riga da sinistra a destra),
    restituisce le coordinate UV per lo SpriteBatch.
    """

    def __init__(self, texture: moderngl.Texture,
                 tile_width: int, tile_height: int,
                 first_gid: int = 1,
                 tile_properties: dict[int, dict[str, Any]] | None = None):
        self.texture = texture
        self.tile_width = tile_width
        self.tile_height = tile_height
        self.first_gid = first_gid
        self.tile_properties: dict[int, dict[str, Any]] = tile_properties or {}

        tex_w, tex_h = texture.size
        self.columns = tex_w // tile_width
        self.rows = tex_h // tile_height
        self.tile_count = self.columns * self.rows

        # Pre-calcola tutte le UV per accesso O(1)
        self._uvs: list[tuple[float, float, float, float]] = []
        for tile_id in range(self.tile_count):
            col = tile_id % self.columns
            row = tile_id // self.columns

            u0 = col * tile_width / tex_w
            u1 = (col + 1) * tile_width / tex_w
            v0 = 1.0 - (row + 1) * tile_height / tex_h
            v1 = 1.0 - row * tile_height / tex_h

            self._uvs.append((u0, v0, u1, v1))

    def contains_gid(self, gid: int) -> bool:
        """True se questo tileset contiene il global tile ID."""
        local = gid - self.first_gid
        return 0 <= local < self.tile_count

    def get_uvs(self, gid: int) -> tuple[float, float, float, float]:
        """Restituisce (u0, v0, u1, v1) per un global tile ID."""
        local = gid - self.first_gid
        return self._uvs[local]

    def get_tile_properties(self, gid: int) -> dict[str, Any]:
        """Restituisce le properties di un tile (dict vuoto se nessuna)."""
        return self.tile_properties.get(gid, {})

    def has_tile_property(self, gid: int, name: str) -> bool:
        """True se il tile ha la property specificata."""
        return name in self.tile_properties.get(gid, {})
