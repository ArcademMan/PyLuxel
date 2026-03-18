import pygame
from pyluxel.input import Input
from pyluxel.ui.widget import Widget, _lerp
from pyluxel.ui.theme import Theme


class Dropdown(Widget):
    """Dropdown selector: header shows current value, click opens option list."""

    def __init__(self, x: float, y: float, w: float, h: float,
                 label: str, options: list, selected: int = 0,
                 theme: Theme = None, on_change=None,
                 click_sound: str | None = None,
                 hover_sound: str | None = None,
                 value: int | None = None,
                 font_size: float | None = None):
        super().__init__(x, y, w, h, theme,
                         click_sound=click_sound, hover_sound=hover_sound,
                         font_size=font_size)
        self.label = label
        self._options = list(options)
        self.value = value if value is not None else selected
        self._on_change_cb = on_change

        self.expanded = False
        self.focused = False
        self._highlight = self.value
        self._option_h = h
        self._option_hovered = -1

    def get_selected_index(self) -> int:
        """Restituisce l'indice dell'opzione selezionata."""
        return self.value

    def set_selected_index(self, idx: int):
        """Imposta l'indice dell'opzione selezionata."""
        self.value = idx

    def selected_text(self) -> str:
        """Restituisce il testo dell'opzione selezionata."""
        return self._options[self.value] if self._options else ""

    def get_options(self) -> list[str]:
        """Restituisce la lista delle opzioni."""
        return self._options

    def select_by_text(self, text: str) -> bool:
        """Seleziona un'opzione per testo. Ritorna True se trovata."""
        for i, opt in enumerate(self._options):
            if opt == text:
                self._select(i)
                return True
        return False

    def add_option(self, text: str, index: int | None = None):
        """Aggiunge un'opzione alla lista."""
        if index is None:
            self._options.append(text)
        else:
            self._options.insert(index, text)

    def remove_option(self, text_or_index: str | int):
        """Rimuove un'opzione per testo o indice."""
        if isinstance(text_or_index, int):
            if 0 <= text_or_index < len(self._options):
                self._options.pop(text_or_index)
                if self.value >= len(self._options):
                    self.value = max(0, len(self._options) - 1)
        else:
            if text_or_index in self._options:
                idx = self._options.index(text_or_index)
                self._options.pop(idx)
                if self.value >= len(self._options):
                    self.value = max(0, len(self._options) - 1)

    def open(self):
        """Espande il menu dropdown."""
        if not self.expanded:
            self.expanded = True
            self.focused = True
            self._highlight = self.value
            self._option_hovered = -1

    def close(self):
        """Chiude il menu dropdown."""
        self._close()

    # --- Event handling ---

    def _option_hit(self, mx_d: float, my_d: float) -> int:
        """Return index of option under mouse, or -1."""
        list_y = self.y + self.h
        if not (self.x <= mx_d <= self.x + self.w):
            return -1
        for i in range(len(self._options)):
            oy = list_y + i * self._option_h
            if oy <= my_d <= oy + self._option_h:
                return i
        return -1

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False

        if self.expanded:
            return self._handle_expanded(event)

        return super().handle_event(event)

    def _handle_expanded(self, event: pygame.event.Event) -> bool:
        """Gestisce solo mouse quando espanso. Keyboard in update()."""
        if event.type == pygame.MOUSEMOTION:
            mx_d, my_d = self._mouse_to_design(event.pos)
            self._hovered = self.hit_test(mx_d, my_d)
            idx = self._option_hit(mx_d, my_d)
            self._option_hovered = idx
            if idx >= 0:
                self._highlight = idx
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx_d, my_d = self._mouse_to_design(event.pos)
            idx = self._option_hit(mx_d, my_d)
            if idx >= 0:
                self._select(idx)
                return True
            # Click on header → close
            if self.hit_test(mx_d, my_d):
                self._close()
                return True
            # Click outside → close
            self._close()
            return False

        return False

    def _on_click(self):
        if not self.expanded:
            self.expanded = True
            self.focused = True
            self._highlight = self.value
            self._option_hovered = -1

    def _close(self):
        self.expanded = False
        self.focused = False

    def _select(self, index: int):
        old = self.value
        self.value = index
        self._close()
        if old != index:
            self._play_sound(self.click_sound)
            if self._on_change_cb:
                self._on_change_cb(index)

    def update(self, dt: float):
        super().update(dt)
        if self.expanded and self._options:
            if Input.pressed("back"):
                self._close()
            elif Input.pressed("nav_up") or Input.pressed("nav_left"):
                self._highlight = (self._highlight - 1) % len(self._options)
            elif Input.pressed("nav_down") or Input.pressed("nav_right"):
                self._highlight = (self._highlight + 1) % len(self._options)
            elif Input.pressed("confirm"):
                self._select(self._highlight)

    def on_adjust(self, direction: int):
        """Called by FocusManager on LEFT/RIGHT when closed — cycles options."""
        if self.expanded or not self._options:
            return
        new = (self.value + direction) % len(self._options)
        self._select(new)

    def covers(self, widget) -> bool:
        """Return True if this dropdown's overlay visually covers the widget."""
        if not self.expanded:
            return False
        ov_top = self.y + self.h
        ov_bot = ov_top + len(self._options) * self._option_h
        return (widget.y + widget.h > ov_top and widget.y < ov_bot
                and widget.x < self.x + self.w and widget.x + widget.w > self.x)

    # --- Drawing: header ---

    def _draw_accent(self, batch):
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
        bg = self._bg_color()
        th = self.theme
        rr.draw(self.x, self.y, self.w, self.h, th.border_radius,
                r=bg[0], g=bg[1], b=bg[2], a=bg[3])

    def draw_bg_accent(self, batch):
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
        th = self.theme

        # Label on the left
        pad = th.padding
        fs = self.scaled_font_size
        font.draw(self.label,
                  self.x + pad, self.y + self.h / 2,
                  size=fs,
                  r=clr[0], g=clr[1], b=clr[2], a=self.alpha,
                  align_y="center")

        # Selected value on the right
        val_text = self.selected_text()
        font.draw(val_text,
                  self.x + self.w - pad, self.y + self.h / 2,
                  size=fs,
                  r=clr[0], g=clr[1], b=clr[2], a=self.alpha,
                  align_x="right", align_y="center")

    # --- Drawing: overlay (option list) ---

    def draw_overlay_bg(self, batch):
        """Draw the expanded option list background. Call AFTER all other widget bgs."""
        if not self.expanded or not self.visible:
            return
        th = self.theme
        list_y = self.y + self.h
        n = len(self._options)
        total_h = n * self._option_h

        # Solid background (fully opaque to cover widgets beneath)
        batch.draw(self.x, list_y, self.w, total_h,
                   r=0.0, g=0.0, b=0.0, a=self.alpha)

        # List background
        bg = th.bg
        batch.draw(self.x, list_y, self.w, total_h,
                   r=bg[0], g=bg[1], b=bg[2], a=self.alpha)

        # Highlighted option
        hy = list_y + self._highlight * self._option_h
        hbg = th.bg_hover
        batch.draw(self.x, hy, self.w, self._option_h,
                   r=hbg[0], g=hbg[1], b=hbg[2], a=hbg[3] * self.alpha)

        # Accent on highlighted
        batch.draw(self.x, hy, th.accent_width_hover, self._option_h,
                   r=th.accent[0], g=th.accent[1], b=th.accent[2], a=0.9 * self.alpha)

    def draw_overlay_text(self, font):
        """Draw the expanded option texts. Call AFTER all other widget texts."""
        if not self.expanded or not self.visible:
            return
        th = self.theme
        list_y = self.y + self.h
        pad = th.padding

        for i, opt in enumerate(self._options):
            oy = list_y + i * self._option_h
            if i == self._highlight:
                clr = th.text_hover
            else:
                clr = th.text
            font.draw(opt,
                      self.x + pad, oy + self._option_h / 2,
                      size=self.scaled_font_size,
                      r=clr[0], g=clr[1], b=clr[2], a=self.alpha,
                      align_y="center")
