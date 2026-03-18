from pyluxel.ui.widget import Widget, _lerp
from pyluxel.ui.theme import Theme


class Toggle(Widget):
    """Toggle on/off con label a sinistra e indicatore a destra."""

    INDICATOR_W = 40.0
    INDICATOR_H_RATIO = 0.5  # altezza indicatore = 50% dell'altezza widget
    KNOB_PADDING = 3.0

    def __init__(self, x: float, y: float, w: float, h: float,
                 label: str, value: bool = False,
                 theme: Theme = None, on_change=None,
                 click_sound: str | None = None,
                 hover_sound: str | None = None,
                 font_size: float | None = None):
        super().__init__(x, y, w, h, theme,
                         click_sound=click_sound, hover_sound=hover_sound,
                         font_size=font_size)
        self.label = label
        self.value = value
        self._on_change_cb = on_change
        self._toggle_t = 1.0 if value else 0.0  # animazione on/off

    def toggle(self):
        """Inverte lo stato del toggle."""
        self.value = not self.value
        if self._on_change_cb:
            self._on_change_cb(self.value)

    def on_adjust(self, direction: int):
        """Called by FocusManager on cross-axis nav — toggles value."""
        self.toggle()

    def _on_click(self):
        self.toggle()

    def update(self, dt: float):
        super().update(dt)
        # Anima transizione on/off
        target = 1.0 if self.value else 0.0
        self._toggle_t += (target - self._toggle_t) * dt * self.theme.anim_speed

    def _draw_indicator(self, batch):
        """Disegna track e knob del toggle nel batch attivo."""
        th = self.theme
        ind_h = self.h * self.INDICATOR_H_RATIO
        ind_x = self.x + self.w - self.INDICATOR_W - th.padding
        ind_y = self.y + (self.h - ind_h) / 2

        # Track del toggle
        track_color = _lerp(th.toggle_off, th.toggle_on, self._toggle_t)
        batch.draw(ind_x, ind_y, self.INDICATOR_W, ind_h,
                   r=track_color[0], g=track_color[1], b=track_color[2],
                   a=track_color[3] * self.alpha)

        # Knob (quadrato che scorre)
        pad = self.KNOB_PADDING
        knob_size = ind_h - pad * 2
        knob_travel = self.INDICATOR_W - knob_size - pad * 2
        knob_x = ind_x + pad + knob_travel * self._toggle_t
        knob_y = ind_y + pad
        batch.draw(knob_x, knob_y, knob_size, knob_size,
                   r=1.0, g=1.0, b=1.0, a=0.95 * self.alpha)

    def draw_bg(self, batch):
        if not self.visible:
            return

        bg = self._bg_color()
        batch.draw(self.x, self.y, self.w, self.h,
                   r=bg[0], g=bg[1], b=bg[2], a=bg[3])
        self._draw_indicator(batch)

    def draw_bg_rounded(self, rr):
        if not self.visible:
            return
        th = self.theme

        bg = self._bg_color()
        rr.draw(self.x, self.y, self.w, self.h, th.border_radius,
                r=bg[0], g=bg[1], b=bg[2], a=bg[3])

    def draw_bg_indicator(self, batch):
        """Disegna indicatore nel batch (chiamare dopo draw_bg_rounded)."""
        if not self.visible:
            return
        self._draw_indicator(batch)

    def draw_text(self, font):
        if not self.visible:
            return
        clr = self._text_current_color()

        # Label a sinistra, centrato verticalmente
        font.draw(self.label,
                  self.x + self.theme.padding, self.y + self.h / 2,
                  size=self.scaled_font_size,
                  r=clr[0], g=clr[1], b=clr[2], a=self.alpha,
                  align_y="center")
