"""Mixin per il rendering testo (SDF fonts con zero-config)."""

from pyluxel.text.fonts import FontManager
from pyluxel.text.sdf_font import SDFFontCache


class _TextMixin:
    """Metodi draw_text / measure_text con auto-flush."""

    def init_fonts(self, fonts_dir: str, font_files: dict[str, str],
                   cache_dir: str | None = None):
        """Configura font custom. Senza questa chiamata usa il font di sistema."""
        FontManager.init(fonts_dir, font_files)
        self._sdf_cache.clear()
        if cache_dir is not None:
            self._sdf_cache = SDFFontCache(self.ctx, self.renderer.sdf_prog, cache_dir=cache_dir)

    def draw_text(self, text: str, x: float, y: float, size: float = 24,
                  font: str = "body",
                  r: float = 1.0, g: float = 1.0, b: float = 1.0, a: float = 1.0,
                  align_x: str = "left", align_y: str = "top"):
        """Disegna testo. Auto-flush a fine frame."""
        sdf_font = self._sdf_cache.get(font)
        sdf_font.draw(text, x, y, size, r, g, b, a, align_x, align_y)

    def measure_text(self, text: str, size: float = 24,
                     font: str = "body") -> tuple[float, float]:
        """Misura testo senza disegnarlo. Ritorna (width, height)."""
        return self._sdf_cache.get(font).measure(text, size)

    def _flush_text(self):
        """Flush tutti i font SDF che hanno testo pendente."""
        for sdf_font in self._sdf_cache._cache.values():
            if sdf_font._count > 0:
                sdf_font.flush()

    def _cleanup_text(self):
        """Rilascia le risorse SDF."""
        from pyluxel.debug import cprint
        try:
            self._sdf_cache.release()
        except Exception as e:
            cprint.warning("App cleanup - sdf_cache:", e)
