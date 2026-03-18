"""GlyphText -- Inline glyph + text rendering with {glyph_name} syntax."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

import moderngl
import pygame

_TOKEN_RE = re.compile(r"\{([^}]+)\}")

# Directory containing bundled PS controller glyphs
_PS_GLYPHS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ps_glyphs")

# Canonical name -> filename mapping per style
_PS_BASIC: dict[str, str] = {
    "cross": "cross.png",
    "circle": "circle.png",
    "square": "square.png",
    "triangle": "triangle.png",
    "dpad_up": "dpad_up.png",
    "dpad_down": "dpad_down.png",
    "dpad_left": "dpad_left.png",
    "dpad_right": "dpad_right.png",
    "L1": "l1.png",
    "L2": "l2.png",
    "L3": "l3.png",
    "R1": "r1.png",
    "R2": "r2.png",
    "R3": "r3.png",
    "share": "share.png",
    "options": "options.png",
}

_PS_ADVANCED: dict[str, str] = {
    "cross": "outline-blue-cross.png",
    "circle": "outline-red-circle.png",
    "square": "outline-purple-square.png",
    "triangle": "outline-green-triangle.png",
    "dpad_up": "outline-top.png",
    "dpad_down": "outline-bottom.png",
    "dpad_left": "outline-left.png",
    "dpad_right": "outline-right.png",
    "L1": "plain-rectangle-L1.png",
    "L2": "plain-rectangle-L2.png",
    "L3": "press-L.png",
    "R1": "plain-rectangle-R1.png",
    "R2": "plain-rectangle-R2.png",
    "R3": "press-R.png",
    "left_stick": "direction-L.png",
    "right_stick": "direction-R.png",
    "share": "outline-share.png",
    "options": "plain-small-option.png",
    "ps": "plain-big-PS.png",
}

_PS_STYLES: dict[str, dict[str, str]] = {
    "basic": _PS_BASIC,
    "advanced": _PS_ADVANCED,
}


def load_ps_glyphs(textures, style: str = "basic") -> None:
    """Load bundled PlayStation controller glyphs into a TextureManager.

    After calling this, glyph names like ``{cross}``, ``{R3}``, ``{dpad_up}``
    are available for use with :class:`GlyphText`.

    Args:
        textures: TextureManager instance.
        style: ``"basic"`` (flat icons) or ``"advanced"`` (outlined/colored).
    """
    mapping = _PS_STYLES.get(style)
    if mapping is None:
        raise ValueError(f"Unknown PS glyph style {style!r}, use 'basic' or 'advanced'")

    style_dir = os.path.join(_PS_GLYPHS_DIR, style)
    for canonical, filename in mapping.items():
        if textures.is_cached(canonical):
            continue
        path = os.path.join(style_dir, filename)
        surface = pygame.image.load(path).convert_alpha()
        tex = textures.surface_to_texture(surface)
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        textures._cache[canonical] = tex


@dataclass(slots=True)
class _TextSeg:
    text: str


@dataclass(slots=True)
class _GlyphSeg:
    name: str


def _parse(text: str) -> list[_TextSeg | _GlyphSeg]:
    """Parse string into text and glyph segments."""
    segments: list[_TextSeg | _GlyphSeg] = []
    last = 0
    for m in _TOKEN_RE.finditer(text):
        if m.start() > last:
            segments.append(_TextSeg(text[last:m.start()]))
        segments.append(_GlyphSeg(m.group(1)))
        last = m.end()
    if last < len(text):
        segments.append(_TextSeg(text[last:]))
    return segments


class GlyphText:
    """Renders mixed text and inline glyph textures.

    Use ``{name}`` syntax to embed textures inline with SDF text::

        gt = GlyphText(batch, font, textures)
        gt.draw("Press {btn_a} to confirm", x, y, size=20)

    Consecutive glyphs ``{a}{b}`` render touching (with small ``glyph_gap``).

    For PlayStation controller glyphs, use the :meth:`ps` factory::

        gt = GlyphText.ps(batch, font, textures, style="basic")
        gt.draw("{cross} Jump  {R3} Crouch", x, y, size=16)
    """

    def __init__(self, batch, font, textures, glyph_gap: float = 2):
        self.batch = batch
        if isinstance(font, str):
            from pyluxel.text.sdf_font import SDFFontCache
            font = SDFFontCache.instance().get(font)
        self.font = font
        self.textures = textures
        self.glyph_gap = glyph_gap

    @classmethod
    def ps(cls, batch, font, textures, style: str = "basic",
           glyph_gap: float = 2) -> GlyphText:
        """Create a GlyphText pre-loaded with PlayStation controller glyphs.

        Args:
            batch: SpriteBatch.
            font: SDFFont or font name string.
            textures: TextureManager.
            style: ``"basic"`` or ``"advanced"``.
            glyph_gap: pixels between consecutive glyphs (default 2).

        Available glyph names:
            ``{cross}`` ``{circle}`` ``{square}`` ``{triangle}``
            ``{dpad_up}`` ``{dpad_down}`` ``{dpad_left}`` ``{dpad_right}``
            ``{L1}`` ``{L2}`` ``{L3}`` ``{R1}`` ``{R2}`` ``{R3}``
            ``{share}`` ``{options}``
            Advanced only: ``{left_stick}`` ``{right_stick}`` ``{ps}``
        """
        load_ps_glyphs(textures, style)
        return cls(batch, font, textures, glyph_gap=glyph_gap)

    def measure(self, text: str, size: float) -> tuple[float, float]:
        """Return (width, height) of the rendered text+glyph string."""
        segments = _parse(text)
        w = 0.0
        h = self.font.get_line_height(size)
        for i, seg in enumerate(segments):
            if isinstance(seg, _TextSeg):
                tw, _ = self.font.measure(seg.text, size)
                w += tw
            else:
                tex = self.textures.load(seg.name)
                glyph_h = size
                glyph_w = glyph_h * (tex.width / tex.height)
                w += glyph_w
                # Add gap only between consecutive glyphs
                if i + 1 < len(segments) and isinstance(segments[i + 1], _GlyphSeg):
                    w += self.glyph_gap
        return w, h

    def draw(self, text: str, x: float, y: float, size: float,
             r: float = 1.0, g: float = 1.0, b: float = 1.0, a: float = 1.0,
             align_x: str = "left", align_y: str = "center"):
        """Draw text with inline glyphs.

        align_x: "left", "center", or "right"
        align_y: "top", "center", or "bottom"
        """
        segments = _parse(text)
        if not segments:
            return

        total_w, total_h = self.measure(text, size)

        # Resolve start_x from alignment
        start_x = x
        if align_x == "center":
            start_x = x - total_w * 0.5
        elif align_x == "right":
            start_x = x - total_w

        cursor_x = start_x
        batch = self.batch
        font = self.font
        textures = self.textures

        for i, seg in enumerate(segments):
            if isinstance(seg, _TextSeg):
                font.draw(seg.text, cursor_x, y, size=size,
                          r=r, g=g, b=b, a=a,
                          align_x="left", align_y=align_y)
                tw, _ = font.measure(seg.text, size)
                cursor_x += tw
            else:
                tex = textures.load(seg.name)
                glyph_h = size
                glyph_w = glyph_h * (tex.width / tex.height)

                # Compute glyph y based on alignment (centered on text)
                if align_y == "center":
                    gy = y - glyph_h * 0.5
                elif align_y == "bottom":
                    gy = y - glyph_h
                else:
                    gy = y

                batch.begin(tex)
                batch.draw(cursor_x, gy, glyph_w, glyph_h, a=a)
                batch.end()

                cursor_x += glyph_w
                # Gap only between consecutive glyphs
                if i + 1 < len(segments) and isinstance(segments[i + 1], _GlyphSeg):
                    cursor_x += self.glyph_gap

        font.flush()
