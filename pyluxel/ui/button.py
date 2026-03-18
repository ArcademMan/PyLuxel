from __future__ import annotations

from pyluxel.ui.widget import Widget, _lerp
from pyluxel.ui.theme import Theme

_HAS_GLYPH = None  # lazy compiled regex


def _contains_glyph(text: str) -> bool:
    global _HAS_GLYPH
    if _HAS_GLYPH is None:
        import re
        _HAS_GLYPH = re.compile(r"\{[^}]+\}")
    return _HAS_GLYPH.search(text) is not None


class Button(Widget):
    """Bottone con accent bar a sinistra e testo centrato.

    Supporta glyph inline (es. ``"{cross} Conferma"``) se viene
    passato un ``GlyphText`` tramite :meth:`set_glyph_text`.
    """

    def __init__(self, x: float, y: float, w: float, h: float,
                 label: str, theme: Theme = None, on_click=None,
                 click_sound: str | None = None,
                 hover_sound: str | None = None,
                 font_size: float | None = None,
                 glyph_text=None):
        super().__init__(x, y, w, h, theme,
                         click_sound=click_sound, hover_sound=hover_sound,
                         font_size=font_size)
        self.label = label
        self._on_click_cb = on_click
        self._glyph_text = glyph_text

    def set_text(self, label: str):
        """Cambia il testo del bottone."""
        self.label = label

    def set_glyph_text(self, glyph_text) -> None:
        """Imposta un GlyphText per il rendering di glyph inline.

        Args:
            glyph_text: istanza di GlyphText (o None per disabilitare).
        """
        self._glyph_text = glyph_text

    def _on_click(self):
        if self._on_click_cb:
            self._on_click_cb()

    def _draw_accent(self, batch):
        """Disegna la accent bar a sinistra (solo se enabled)."""
        if not self.enabled:
            return
        t = self._hover_t
        th = self.theme
        ac = self._accent_color()
        aw = th.accent_width + (th.accent_width_hover - th.accent_width) * t
        accent_a = (0.85 + t * 0.15) * self.alpha
        batch.draw(self.x, self.y, aw, self.h,
                   r=ac[0], g=ac[1], b=ac[2], a=accent_a)

    def draw_bg(self, batch):
        if not self.visible:
            return

        bg = self._bg_color()
        batch.draw(self.x, self.y, self.w, self.h,
                   r=bg[0], g=bg[1], b=bg[2], a=bg[3])
        self._draw_accent(batch)

    def draw_bg_rounded(self, rr):
        if not self.visible:
            return
        th = self.theme

        bg = self._bg_color()
        rr.draw(self.x, self.y, self.w, self.h, th.border_radius,
                r=bg[0], g=bg[1], b=bg[2], a=bg[3])

    def draw_bg_accent(self, batch):
        """Disegna accent bar nel batch (chiamare dopo draw_bg_rounded)."""
        if not self.visible or not self.enabled:
            return
        t = self._hover_t
        th = self.theme
        ac = self._accent_color()
        aw = th.accent_width + (th.accent_width_hover - th.accent_width) * t
        accent_a = (0.85 + t * 0.15) * self.alpha
        inset = th.border_radius * 0.3
        batch.draw(self.x + inset, self.y + inset, aw, self.h - inset * 2,
                   r=ac[0], g=ac[1], b=ac[2], a=accent_a)

    def draw_text(self, font):
        if not self.visible:
            return
        clr = self._text_current_color()
        cx = self.x + self.w / 2
        cy = self.y + self.h / 2
        size = self.scaled_font_size

        if self._glyph_text is not None and _contains_glyph(self.label):
            self._glyph_text.draw(
                self.label, cx, cy, size=size,
                r=clr[0], g=clr[1], b=clr[2], a=self.alpha,
                align_x="center", align_y="center")
        else:
            font.draw(self.label, cx, cy, size=size,
                      r=clr[0], g=clr[1], b=clr[2], a=self.alpha,
                      align_x="center", align_y="center")
