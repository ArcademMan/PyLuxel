"""pyluxel.ui -- Toolkit UI riusabile con tema neutro di default."""

from pyluxel.ui.theme import Theme
from pyluxel.ui.widget import Widget
from pyluxel.ui.button import Button
from pyluxel.ui.toggle import Toggle
from pyluxel.ui.slider import Slider
from pyluxel.ui.line_edit import LineEdit
from pyluxel.ui.dropdown import Dropdown
from pyluxel.ui.rounded_rect import RoundedRectRenderer
from pyluxel.ui.focus import FocusManager
from pyluxel.ui.layout import VBox, HBox, _BoxBase
from pyluxel.ui.glyph_text import GlyphText, load_ps_glyphs


def _flatten(widgets):
    """Espande ricorsivamente i box in widget foglia."""
    result = []
    for w in widgets:
        if isinstance(w, _BoxBase):
            result.extend(w.flat_widgets())
        else:
            result.append(w)
    return result


def render_widgets(widgets, batch, white_tex, font, rounded=None):
    """Renderizza una lista di widget in modo efficiente.

    font può essere un oggetto SDFFont oppure una stringa (nome del font),
    nel qual caso viene risolto tramite SDFFontCache.

    Se rounded è fornito (RoundedRectRenderer), i widget con border_radius > 0
    usano angoli arrotondati GPU-accelerati.

    Supporta box innestati (VBox/HBox): vengono espansi automaticamente.
    """
    if isinstance(font, str):
        from pyluxel.text.sdf_font import SDFFontCache
        font = SDFFontCache.instance().get(font)

    widgets = _flatten(widgets)
    has_rounded = rounded is not None

    # Fase 1: Background con angoli netti (batched)
    batch.begin(white_tex)
    for w in widgets:
        if not w.visible:
            continue
        if has_rounded and w.theme.border_radius > 0:
            # I toggle e slider hanno parti interne (knob, track)
            # che vanno disegnate nel batch anche con rounded bg
            pass
        else:
            w.draw_bg(batch)
    batch.end()

    # Fase 2: Background con angoli arrotondati (un draw call ciascuno)
    if has_rounded:
        for w in widgets:
            if w.visible and w.theme.border_radius > 0:
                w.draw_bg_rounded(rounded)

        # Fase 2b: Elementi interni (knob, track, selezione) nel batch
        batch.begin(white_tex)
        for w in widgets:
            if not w.visible or w.theme.border_radius <= 0:
                continue
            if hasattr(w, 'draw_bg_accent'):
                w.draw_bg_accent(batch)
            if hasattr(w, 'draw_bg_indicator'):
                w.draw_bg_indicator(batch)
            if hasattr(w, 'draw_bg_track'):
                w.draw_bg_track(batch)
            if hasattr(w, 'draw_bg_selection'):
                w.draw_bg_selection(batch)
        batch.end()

    # Trova dropdown espansi per skippare testi coperti
    expanded = [w for w in widgets if isinstance(w, Dropdown) and w.expanded]

    # Fase 3: Testo (salta widget coperti da dropdown overlay)
    for w in widgets:
        if not w.visible:
            continue
        if expanded and any(dd.covers(w) for dd in expanded):
            continue
        w.draw_text(font)
    font.flush()

    # Fase 4: Dropdown overlay (bg + testo opzioni)
    if expanded:
        batch.begin(white_tex)
        for dd in expanded:
            dd.draw_overlay_bg(batch)
        batch.end()
        for dd in expanded:
            dd.draw_overlay_text(font)
        font.flush()


__all__ = [
    "Theme",
    "Widget",
    "Button",
    "Toggle",
    "Slider",
    "LineEdit",
    "Dropdown",
    "RoundedRectRenderer",
    "FocusManager",
    "VBox",
    "HBox",
    "render_widgets",
    "GlyphText",
    "load_ps_glyphs",
]
