import pygame
from pyluxel.ui.widget import Widget, _lerp
from pyluxel.ui.theme import Theme


class Slider(Widget):
    """Slider orizzontale con handle trascinabile."""

    def __init__(self, x: float, y: float, w: float, h: float,
                 label: str, value: float = 0.0,
                 min_val: float = 0.0, max_val: float = 1.0,
                 step: float = 0.0,
                 theme: Theme = None, on_change=None,
                 click_sound: str | None = None,
                 hover_sound: str | None = None,
                 font_size: float | None = None):
        super().__init__(x, y, w, h, theme,
                         click_sound=click_sound, hover_sound=hover_sound,
                         font_size=font_size)
        self.label = label
        self.value = value
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self._on_change_cb = on_change
        self._dragging = False
        self._initial_value = value

    def reset(self):
        """Ripristina lo slider al valore iniziale."""
        self.value = self._initial_value
        if self._on_change_cb:
            self._on_change_cb(self.value)

    def set_range(self, min_val: float, max_val: float):
        """Imposta il range dello slider."""
        self.min_val = min_val
        self.max_val = max_val
        self.value = max(min_val, min(max_val, self.value))

    def is_dragging(self) -> bool:
        """True se lo slider e' in fase di trascinamento."""
        return self._dragging

    def get_normalized_value(self) -> float:
        """Ritorna il valore normalizzato [0-1]."""
        return self._value_to_ratio()

    def set_normalized_value(self, ratio: float):
        """Imposta il valore da un ratio normalizzato [0-1]."""
        new_val = self._ratio_to_value(max(0.0, min(1.0, ratio)))
        if new_val != self.value:
            self.value = new_val
            if self._on_change_cb:
                self._on_change_cb(self.value)

    def _value_to_ratio(self) -> float:
        rng = self.max_val - self.min_val
        if rng == 0:
            return 0.0
        return (self.value - self.min_val) / rng

    def _ratio_to_value(self, ratio: float) -> float:
        val = self.min_val + ratio * (self.max_val - self.min_val)
        if self.step > 0:
            val = round(val / self.step) * self.step
        return max(self.min_val, min(self.max_val, val))

    def _track_rect(self) -> tuple:
        """Ritorna (x, y, w, h) della track in design space."""
        th = self.theme
        pad = th.padding
        track_w = self.w - pad * 2
        track_x = self.x + pad
        track_y = self.y + self.h - th.track_height - pad * 0.67
        return track_x, track_y, track_w, th.track_height

    def _set_value_from_mouse(self, mx_d: float):
        tx, _, tw, _ = self._track_rect()
        ratio = (mx_d - tx) / tw
        ratio = max(0.0, min(1.0, ratio))
        new_val = self._ratio_to_value(ratio)
        if new_val != self.value:
            self.value = new_val
            if self._on_change_cb:
                self._on_change_cb(self.value)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False

        if event.type == pygame.MOUSEMOTION:
            mx_d, my_d = self._mouse_to_design(event.pos)
            was_hovered = self._hovered
            self._hovered = self.hit_test(mx_d, my_d)
            if self._hovered and not was_hovered:
                self._play_sound(self.hover_sound)
            if self._dragging:
                self._set_value_from_mouse(mx_d)
                return True
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx_d, my_d = self._mouse_to_design(event.pos)
            if self.hit_test(mx_d, my_d):
                self._dragging = True
                self._play_sound(self.click_sound)
                self._set_value_from_mouse(mx_d)
                return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging:
                self._dragging = False
                return True

        return False

    def on_adjust(self, direction: int):
        """Called by FocusManager on cross-axis nav — adjusts slider value."""
        step = self.step if self.step > 0 else (self.max_val - self.min_val) * 0.05
        new_val = self.value + direction * step
        new_val = max(self.min_val, min(self.max_val, new_val))
        if new_val != self.value:
            self.value = new_val
            if self._on_change_cb:
                self._on_change_cb(self.value)

    def _on_click(self):
        pass  # gestito in handle_event

    def _draw_track_and_handle(self, batch):
        th = self.theme
        t = self._hover_t

        # Track
        tx, ty, tw, tht = self._track_rect()
        tc = th.track_color
        batch.draw(tx, ty, tw, tht,
                   r=tc[0], g=tc[1], b=tc[2], a=tc[3] * self.alpha)

        # Filled portion
        ratio = self._value_to_ratio()
        filled_w = max(0.0, tw * ratio)
        ac = th.handle_color
        batch.draw(tx, ty, filled_w, tht,
                   r=ac[0], g=ac[1], b=ac[2], a=ac[3] * self.alpha)

        # Handle
        hs = th.handle_size
        hx = tx + filled_w - hs / 2
        hy = ty + tht / 2 - hs / 2
        handle_a = (0.9 + t * 0.1) * self.alpha
        batch.draw(hx, hy, hs, hs,
                   r=ac[0], g=ac[1], b=ac[2], a=handle_a)

    def draw_bg(self, batch):
        if not self.visible:
            return
        th = self.theme

        bg = self._bg_color()
        batch.draw(self.x, self.y, self.w, self.h,
                   r=bg[0], g=bg[1], b=bg[2], a=bg[3])
        self._draw_track_and_handle(batch)

    def draw_bg_rounded(self, rr):
        if not self.visible:
            return
        th = self.theme

        bg = self._bg_color()
        rr.draw(self.x, self.y, self.w, self.h, th.border_radius,
                r=bg[0], g=bg[1], b=bg[2], a=bg[3])
        # Track e handle restano rettangolari (sono interni al widget)

    def draw_bg_track(self, batch):
        """Disegna track e handle nel batch (chiamare dopo draw_bg_rounded)."""
        if not self.visible:
            return
        self._draw_track_and_handle(batch)

    def draw_text(self, font):
        if not self.visible:
            return
        clr = self._text_current_color()
        th = self.theme

        # Label a sinistra
        pad = th.padding
        fs = self.scaled_font_size
        font.draw(self.label,
                  self.x + pad, self.y + pad * 0.5 + fs * 0.5,
                  size=fs,
                  r=clr[0], g=clr[1], b=clr[2], a=self.alpha,
                  align_y="center")

        # Valore a destra
        if self.step >= 1.0:
            val_text = str(int(self.value))
        else:
            val_text = f"{self.value:.2f}"
        val_size = fs * 0.85
        font.draw(val_text,
                  self.x + self.w - pad, self.y + pad * 0.5 + fs * 0.5,
                  size=val_size,
                  r=clr[0], g=clr[1], b=clr[2], a=self.alpha,
                  align_x="right", align_y="center")
