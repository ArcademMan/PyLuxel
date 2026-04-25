import pygame
import moderngl

from pyluxel.core import paths
from pyluxel.core.pak import asset_open


class TextureManager:
    """Carica e cacha texture GPU da file PNG."""

    def __init__(self, ctx: moderngl.Context, base_path: str = "assets/sprites"):
        self.ctx = ctx
        self.base_path = base_path
        self._cache: dict[str, moderngl.Texture] = {}

    def load(self, name: str) -> moderngl.Texture:
        """Carica una texture da PNG. Usa cache se già caricata."""
        if name in self._cache:
            return self._cache[name]

        path = paths.join(self.base_path, name)
        if not path.endswith(".png"):
            path += ".png"

        surface = pygame.image.load(asset_open(path)).convert_alpha()
        texture = self.surface_to_texture(surface)
        self._cache[name] = texture
        return texture

    def surface_to_texture(self, surface: pygame.Surface) -> moderngl.Texture:
        """Converte una pygame.Surface in una texture ModernGL."""
        # pygame surface -> bytes (RGBA)
        data = pygame.image.tobytes(surface, "RGBA", True)
        w, h = surface.get_size()

        texture = self.ctx.texture((w, h), 4, data)
        texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
        texture.repeat_x = False
        texture.repeat_y = False
        texture.swizzle = "RGBA"
        return texture

    def create_from_color(self, width: int, height: int,
                          color: tuple[int, ...] = (255, 255, 255, 255)) -> moderngl.Texture:
        """Crea una texture tinta unita (utile per quad senza texture). Cachata."""
        key = f"__color_{width}x{height}_{color}"
        if key in self._cache:
            return self._cache[key]
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        surface.fill(color)
        texture = self.surface_to_texture(surface)
        self._cache[key] = texture
        return texture

    def release(self, name: str):
        """Rilascia una texture dalla cache e dalla GPU."""
        if name in self._cache:
            self._cache[name].release()
            del self._cache[name]

    def is_cached(self, name: str) -> bool:
        """Controlla se una texture e' gia' caricata in cache."""
        return name in self._cache

    def get_cached_names(self) -> list[str]:
        """Ritorna la lista dei nomi delle texture in cache."""
        return list(self._cache.keys())

    def reload(self, name: str) -> moderngl.Texture:
        """Ricarica forzatamente una texture da disco (utile per hot-reload)."""
        if name in self._cache:
            self._cache[name].release()
            del self._cache[name]
        return self.load(name)

    def release_all(self):
        """Rilascia tutte le texture."""
        for tex in self._cache.values():
            tex.release()
        self._cache.clear()
