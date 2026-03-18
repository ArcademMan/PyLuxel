import pygame
from pyluxel.core.resolution import Resolution
from pyluxel.ui.theme import Theme

# Singleton risoluzione per conversione coordinate mouse
_R = Resolution()

# Import lazy del singleton Sound per evitare import circolari
_sound_manager = None


def _get_sound():
    global _sound_manager
    if _sound_manager is None:
        from pyluxel.audio import Sound
        _sound_manager = Sound
    return _sound_manager


def _lerp(a, b, t):
    """Interpolazione lineare tra due tuple."""
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(len(a)))


class Widget:
    """Classe base per tutti i widget UI. Coordinate in design space."""

    def __init__(self, x: float, y: float, w: float, h: float,
                 theme: Theme = None,
                 click_sound: str | None = None,
                 hover_sound: str | None = None,
                 bg: tuple | None = None,
                 bg_hover: tuple | None = None,
                 bg_disabled: tuple | None = None,
                 accent: tuple | None = None,
                 text_color: tuple | None = None,
                 text_hover: tuple | None = None,
                 text_disabled: tuple | None = None,
                 font_size: float | None = None):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.theme = theme or Theme()
        self.visible = True
        self.enabled = True
        self.alpha = 1.0  # global opacity: 0.0 = invisible, 1.0 = fully opaque
        self.selected = False  # selezione esterna (tastiera/navigazione)
        self._hover_t = 0.0
        self._hovered = False
        self._pressed = False
        self.click_sound = click_sound
        self.hover_sound = hover_sound
        self._font_size = font_size
        # Per-widget color overrides (None = use theme)
        self._bg = bg
        self._bg_hover = bg_hover
        self._bg_disabled = bg_disabled
        self._accent = accent
        self._text_color = text_color
        self._text_hover = text_hover
        self._text_disabled = text_disabled

    def is_hovered(self) -> bool:
        """True se il mouse e' sopra il widget."""
        return self._hovered

    def is_pressed(self) -> bool:
        """True se il widget e' premuto."""
        return self._pressed

    def set_position(self, x: float, y: float):
        """Imposta la posizione del widget."""
        self.x = x
        self.y = y

    def set_size(self, w: float, h: float):
        """Imposta le dimensioni del widget."""
        self.w = w
        self.h = h

    def set_bg_color(self, bg: tuple, bg_hover: tuple = None, bg_disabled: tuple = None):
        """Imposta i colori di background per questo widget."""
        self._bg = bg
        if bg_hover is not None:
            self._bg_hover = bg_hover
        if bg_disabled is not None:
            self._bg_disabled = bg_disabled

    def set_text_color(self, text: tuple, text_hover: tuple = None, text_disabled: tuple = None):
        """Imposta i colori del testo per questo widget."""
        self._text_color = text
        if text_hover is not None:
            self._text_hover = text_hover
        if text_disabled is not None:
            self._text_disabled = text_disabled

    def set_accent_color(self, accent: tuple):
        """Imposta il colore accent per questo widget."""
        self._accent = accent

    def set_font_size(self, size: float):
        """Imposta una dimensione fissa del font per questo widget."""
        self._font_size = size

    def show(self):
        """Rende il widget visibile."""
        self.visible = True

    def hide(self):
        """Nasconde il widget."""
        self.visible = False

    def enable(self):
        """Abilita il widget."""
        self.enabled = True

    def disable(self):
        """Disabilita il widget."""
        self.enabled = False

    def hit_test(self, mx_d: float, my_d: float) -> bool:
        """Testa se le coordinate design-space sono dentro il widget."""
        return (self.x <= mx_d <= self.x + self.w
                and self.y <= my_d <= self.y + self.h)

    def _mouse_to_design(self, pos: tuple) -> tuple:
        """Converte coordinate mouse (screen) in design space."""
        return pos[0] / _R.scale, pos[1] / _R.scale

    def _play_sound(self, name: str | None) -> None:
        """Riproduce un suono se il nome e' valido e caricato."""
        if name:
            _get_sound().play(name)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Processa un evento pygame. Ritorna True se consumato."""
        if not self.visible or not self.enabled:
            return False

        if event.type == pygame.MOUSEMOTION:
            mx_d, my_d = self._mouse_to_design(event.pos)
            was_hovered = self._hovered
            self._hovered = self.hit_test(mx_d, my_d)
            if self._hovered and not was_hovered:
                self._play_sound(self.hover_sound)
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx_d, my_d = self._mouse_to_design(event.pos)
            if self.hit_test(mx_d, my_d):
                self._pressed = True
                return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._pressed:
                self._pressed = False
                mx_d, my_d = self._mouse_to_design(event.pos)
                if self.hit_test(mx_d, my_d):
                    self._play_sound(self.click_sound)
                    self._on_click()
                    return True

        return False

    def _on_click(self):
        """Chiamato quando il widget viene cliccato. Override nelle sottoclassi."""
        pass

    def update(self, dt: float):
        """Aggiorna animazione hover."""
        target = 1.0 if (self._hovered or self.selected) and self.enabled else 0.0
        self._hover_t += (target - self._hover_t) * dt * self.theme.anim_speed

    def _apply_alpha(self, a: float) -> float:
        """Moltiplica un valore alpha per self.alpha."""
        return a * self.alpha

    def _bg_color(self):
        """Colore background corrente (tiene conto di enabled, hover e alpha)."""
        if not self.enabled:
            c = self._bg_disabled or self.theme.bg_disabled
        else:
            bg = self._bg or self.theme.bg
            bg_h = self._bg_hover or self.theme.bg_hover
            c = _lerp(bg, bg_h, self._hover_t)
        return (c[0], c[1], c[2], c[3] * self.alpha)

    def _accent_color(self):
        """Colore accent corrente."""
        return self._accent or self.theme.accent

    @property
    def scaled_font_size(self) -> float:
        """Font size: override per-widget > auto-scale da altezza widget."""
        if self._font_size is not None:
            return self._font_size
        return self.theme.font_size * (self.h / self.theme.font_ref_height)

    def _text_current_color(self):
        """Colore testo corrente (tiene conto di enabled e hover)."""
        if not self.enabled:
            return self._text_disabled or self.theme.text_disabled
        t_normal = self._text_color or self.theme.text
        t_hover = self._text_hover or self.theme.text_hover
        return _lerp(t_normal, t_hover, self._hover_t)

    def draw_bg(self, batch):
        """Disegna il background nel batch attivo. Override per aspetto custom."""
        pass

    def draw_bg_rounded(self, rr):
        """Disegna il background con angoli arrotondati via RoundedRectRenderer."""
        pass

    def draw_text(self, font):
        """Disegna il testo con il font. Override per testo custom."""
        pass
