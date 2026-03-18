import pygame
import moderngl

from pyluxel.debug import cprint

# Fattore di oversampling: i glifi vengono renderizzati a questa moltiplicazione
# rispetto alla size richiesta, poi la GPU scala giù con LINEAR filtering.
OVERSAMPLE = 2


class BitmapFont:
    """Font renderizzato come texture atlas su GPU con oversampling.

    All'init genera un atlas con tutti i glifi ASCII stampabili (32-126)
    a risoluzione 2x, con LINEAR filtering per anti-aliasing pulito.
    A runtime disegna testo come batch di quad — zero transfer CPU→GPU.
    """

    CHARS = [chr(c) for c in range(32, 127)]

    def __init__(self, ctx: moderngl.Context, sprite_prog: moderngl.Program,
                 pygame_font: pygame.font.Font, requested_size: int):
        self.ctx = ctx
        self.prog = sprite_prog
        self._requested_size = requested_size

        hi_res_size = requested_size * OVERSAMPLE
        try:
            hi_font = pygame.font.Font(pygame_font.name, hi_res_size)
        except (TypeError, FileNotFoundError) as e:
            cprint.warning("BitmapFont hi-res fallback:", e)
            hi_font = pygame.font.Font(None, hi_res_size)

        glyphs = {}
        max_h = 0
        total_w = 0
        for ch in self.CHARS:
            surf = hi_font.render(ch, True, (255, 255, 255))
            glyphs[ch] = surf
            total_w += surf.get_width()
            max_h = max(max_h, surf.get_height())

        self.glyph_height = max_h / OVERSAMPLE

        atlas_surface = pygame.Surface((total_w, max_h), pygame.SRCALPHA)
        atlas_surface.fill((0, 0, 0, 0))

        self._uv_map: dict[str, tuple[float, float, float, float]] = {}
        self._widths: dict[str, float] = {}
        x_cursor = 0
        for ch in self.CHARS:
            surf = glyphs[ch]
            w = surf.get_width()
            atlas_surface.blit(surf, (x_cursor, 0))

            u0 = x_cursor / total_w
            u1 = (x_cursor + w) / total_w
            self._uv_map[ch] = (u0, 0.0, u1, 1.0)
            self._widths[ch] = w / OVERSAMPLE

            x_cursor += w

        data = pygame.image.tobytes(atlas_surface, "RGBA", True)
        self.atlas = ctx.texture((total_w, max_h), 4, data)
        self.atlas.filter = (moderngl.LINEAR, moderngl.LINEAR)

        self.atlas_width = total_w
        self.atlas_height = max_h

    def get_glyph_width(self, char: str) -> float:
        """Ritorna la larghezza di un singolo glifo."""
        return self._widths.get(char, 0)

    def get_line_height(self) -> float:
        """Ritorna l'altezza di una riga."""
        return self.glyph_height

    def has_char(self, char: str) -> bool:
        """True se il carattere e' supportato dall'atlas."""
        return char in self._uv_map

    def measure(self, text: str) -> tuple[float, float]:
        """Misura la larghezza e altezza del testo in design coords."""
        w = sum(self._widths.get(ch, 0) for ch in text)
        return (w, self.glyph_height)

    def draw(self, batch, text: str, x: float, y: float,
             r: float = 1.0, g: float = 1.0, b: float = 1.0, a: float = 1.0,
             align_x: str = "left", align_y: str = "top"):
        """Disegna testo usando lo sprite batch (deve essere già begun con self.atlas)."""
        if align_x != "left" or align_y != "top":
            tw, th = self.measure(text)
            if align_x == "center":
                x -= tw / 2
            elif align_x == "right":
                x -= tw
            if align_y == "center":
                y -= th / 2
            elif align_y == "bottom":
                y -= th

        cursor_x = x
        h = self.glyph_height

        for ch in text:
            if ch not in self._uv_map:
                ch = "?"
            if ch == " ":
                cursor_x += self._widths.get(" ", 4)
                continue

            u0, v0, u1, v1 = self._uv_map[ch]
            w = self._widths[ch]

            batch.draw(cursor_x, y, w, h,
                       u0=u0, v0=v0, u1=u1, v1=v1,
                       r=r, g=g, b=b, a=a)

            cursor_x += w

    def release(self):
        """Rilascia la texture atlas dalla GPU."""
        self.atlas.release()


class FontCache:
    """Cache di BitmapFont per diverse dimensioni.

    Genera i BitmapFont on-demand e li cacha.
    Ogni font+size = un atlas texture sulla GPU, creato una volta sola.
    """

    def __init__(self, ctx: moderngl.Context, sprite_prog: moderngl.Program):
        self.ctx = ctx
        self.prog = sprite_prog
        self._cache: dict[tuple[str, int], BitmapFont] = {}

    def get(self, font_name: str, size: int) -> BitmapFont:
        """Ottieni un BitmapFont cachato. Creato al primo accesso."""
        key = (font_name, size)
        if key not in self._cache:
            from pyluxel.text.fonts import FontManager
            fm = FontManager()
            pg_font = fm.get(font_name, size)
            self._cache[key] = BitmapFont(self.ctx, self.prog, pg_font, size)
        return self._cache[key]

    def list_cached_fonts(self) -> list[tuple[str, int]]:
        """Ritorna la lista dei font+size caricati in cache."""
        return list(self._cache.keys())

    def clear(self):
        """Rilascia tutte le texture atlas (chiamare dopo cambio risoluzione)."""
        for bf in self._cache.values():
            try:
                bf.release()
            except Exception as e:
                cprint.warning("Font cache release failed:", e)
        self._cache.clear()

    def release(self):
        """Alias per clear."""
        self.clear()
