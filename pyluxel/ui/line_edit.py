import pygame
from pyluxel.ui.widget import Widget, _lerp
from pyluxel.ui.theme import Theme
from pyluxel.debug import cprint


class LineEdit(Widget):
    """Campo di input testo con cursore, selezione, clipboard e scrolling."""

    CURSOR_BLINK_RATE = 0.53
    REPEAT_DELAY = 0.4     # secondi prima del repeat
    REPEAT_INTERVAL = 0.035  # secondi tra ogni repeat

    def __init__(self, x: float, y: float, w: float, h: float,
                 placeholder: str = "", text: str = "",
                 max_length: int = 0, font=None,
                 theme: Theme = None, on_change=None, on_submit=None,
                 click_sound: str | None = None,
                 hover_sound: str | None = None,
                 font_size: float | None = None):
        super().__init__(x, y, w, h, theme,
                         click_sound=click_sound, hover_sound=hover_sound,
                         font_size=font_size)
        self.text = text
        self.placeholder = placeholder
        self.max_length = max_length
        self._font = font  # riferimento SDFFont per misurazioni
        self._on_change_cb = on_change
        self._on_submit_cb = on_submit
        self.focused = False
        self._cursor_pos = len(text)
        self._sel_start = 0
        self._sel_end = 0
        self._cursor_timer = 0.0
        self._cursor_visible = True
        self._scroll_x = 0.0  # offset di scroll orizzontale

        # Key repeat manuale
        self._repeat_key = None
        self._repeat_timer = 0.0
        self._repeat_mods = 0

    def clear(self):
        """Svuota il testo."""
        self.text = ""
        self._cursor_pos = 0
        self._sel_start = self._sel_end = 0
        self._scroll_x = 0.0
        self._notify_change()

    def select_all(self):
        """Seleziona tutto il testo."""
        self._sel_start = 0
        self._sel_end = len(self.text)
        self._cursor_pos = len(self.text)

    def get_cursor_pos(self) -> int:
        """Ritorna la posizione corrente del cursore."""
        return self._cursor_pos

    def set_cursor_pos(self, pos: int):
        """Imposta la posizione del cursore."""
        self._cursor_pos = max(0, min(len(self.text), pos))
        self._sel_start = self._sel_end = self._cursor_pos
        self._reset_blink()
        self._ensure_cursor_visible()

    def insert_text(self, txt: str):
        """Inserisce testo alla posizione corrente del cursore."""
        self._insert_text(txt)
        self._notify_change()
        self._ensure_cursor_visible()

    def deselect(self):
        """Rimuove la selezione senza eliminare il testo."""
        self._sel_start = self._sel_end = self._cursor_pos

    @property
    def has_selection(self) -> bool:
        return self._sel_start != self._sel_end

    @property
    def selection_range(self) -> tuple:
        return (min(self._sel_start, self._sel_end),
                max(self._sel_start, self._sel_end))

    def _on_click(self):
        """Attiva focus (usato dal FocusManager via ENTER)."""
        self.focused = True
        self._reset_blink()
        self._sel_start = 0
        self._sel_end = len(self.text)
        self._cursor_pos = len(self.text)
        self._ensure_cursor_visible()

    def _visible_width(self) -> float:
        return self.w - self.theme.padding * 2

    def _delete_selection(self):
        lo, hi = self.selection_range
        self.text = self.text[:lo] + self.text[hi:]
        self._cursor_pos = lo
        self._sel_start = self._sel_end = lo

    def _insert_text(self, txt: str):
        if self.has_selection:
            self._delete_selection()
        if self.max_length > 0 and len(self.text) + len(txt) > self.max_length:
            txt = txt[:self.max_length - len(self.text)]
        self.text = self.text[:self._cursor_pos] + txt + self.text[self._cursor_pos:]
        self._cursor_pos += len(txt)
        self._sel_start = self._sel_end = self._cursor_pos

    def _notify_change(self):
        if self._on_change_cb:
            self._on_change_cb(self.text)

    def _reset_blink(self):
        self._cursor_timer = 0.0
        self._cursor_visible = True

    def _measure_to(self, pos: int) -> float:
        """Larghezza del testo fino a pos, usando il font memorizzato."""
        if not self._font or pos <= 0:
            return 0.0
        tw, _ = self._font.measure(self.text[:pos], self.scaled_font_size)
        return tw

    def _ensure_cursor_visible(self):
        """Aggiorna _scroll_x per mantenere il cursore visibile."""
        cursor_x = self._measure_to(self._cursor_pos)
        vis_w = self._visible_width()

        if cursor_x - self._scroll_x > vis_w:
            self._scroll_x = cursor_x - vis_w
        elif cursor_x - self._scroll_x < 0:
            self._scroll_x = cursor_x
        self._scroll_x = max(0.0, self._scroll_x)

    def _process_key(self, key, mods=0):
        """Processa un tasto (usato sia da handle_event che dal repeat)."""
        ctrl = mods & pygame.KMOD_CTRL
        shift = mods & pygame.KMOD_SHIFT
        self._reset_blink()

        if key == pygame.K_LEFT:
            if self._cursor_pos > 0:
                if shift:
                    self._sel_end = self._cursor_pos - 1
                elif self.has_selection:
                    lo, _ = self.selection_range
                    self._sel_start = self._sel_end = lo
                    self._cursor_pos = lo
                    self._ensure_cursor_visible()
                    return
                else:
                    self._sel_start = self._sel_end = self._cursor_pos - 1
                self._cursor_pos -= 1
            self._ensure_cursor_visible()
            return

        if key == pygame.K_RIGHT:
            if self._cursor_pos < len(self.text):
                if shift:
                    self._sel_end = self._cursor_pos + 1
                elif self.has_selection:
                    _, hi = self.selection_range
                    self._sel_start = self._sel_end = hi
                    self._cursor_pos = hi
                    self._ensure_cursor_visible()
                    return
                else:
                    self._sel_start = self._sel_end = self._cursor_pos + 1
                self._cursor_pos += 1
            self._ensure_cursor_visible()
            return

        if key == pygame.K_HOME:
            if shift:
                self._sel_end = 0
            else:
                self._sel_start = self._sel_end = 0
            self._cursor_pos = 0
            self._ensure_cursor_visible()
            return

        if key == pygame.K_END:
            end = len(self.text)
            if shift:
                self._sel_end = end
            else:
                self._sel_start = self._sel_end = end
            self._cursor_pos = end
            self._ensure_cursor_visible()
            return

        if key == pygame.K_BACKSPACE:
            if self.has_selection:
                self._delete_selection()
            elif self._cursor_pos > 0:
                self.text = self.text[:self._cursor_pos - 1] + self.text[self._cursor_pos:]
                self._cursor_pos -= 1
                self._sel_start = self._sel_end = self._cursor_pos
            self._notify_change()
            self._ensure_cursor_visible()
            return

        if key == pygame.K_DELETE:
            if self.has_selection:
                self._delete_selection()
            elif self._cursor_pos < len(self.text):
                self.text = self.text[:self._cursor_pos] + self.text[self._cursor_pos + 1:]
            self._notify_change()
            self._ensure_cursor_visible()
            return

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False

        # Hover
        if event.type == pygame.MOUSEMOTION:
            mx_d, my_d = self._mouse_to_design(event.pos)
            was_hovered = self._hovered
            self._hovered = self.hit_test(mx_d, my_d)
            if self._hovered and not was_hovered:
                self._play_sound(self.hover_sound)
            return False

        # Click per focus
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx_d, my_d = self._mouse_to_design(event.pos)
            was_focused = self.focused
            self.focused = self.hit_test(mx_d, my_d)
            if self.focused:
                self._reset_blink()
                if not was_focused:
                    self._play_sound(self.click_sound)
                    self._sel_start = 0
                    self._sel_end = len(self.text)
                    self._cursor_pos = len(self.text)
                    self._ensure_cursor_visible()
                return True
            return False

        if not self.focused:
            return False

        # Key up: stop repeat
        if event.type == pygame.KEYUP:
            if self._repeat_key == event.key:
                self._repeat_key = None
            return False

        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl = mods & pygame.KMOD_CTRL
            shift = mods & pygame.KMOD_SHIFT

            # Ctrl shortcuts (no repeat)
            if ctrl and event.key == pygame.K_a:
                self._sel_start = 0
                self._sel_end = len(self.text)
                self._cursor_pos = len(self.text)
                return True

            if ctrl and event.key == pygame.K_c:
                if self.has_selection:
                    lo, hi = self.selection_range
                    try:
                        pygame.scrap.put_text(self.text[lo:hi])
                    except Exception as e:
                        cprint.warning("Clipboard copy failed:", e)
                return True

            if ctrl and event.key == pygame.K_v:
                try:
                    clip = pygame.scrap.get_text()
                except Exception as e:
                    cprint.warning("Clipboard paste failed:", e)
                    clip = None
                if clip:
                    clip = clip.replace("\n", "").replace("\r", "")
                    self._insert_text(clip)
                    self._notify_change()
                    self._ensure_cursor_visible()
                return True

            if ctrl and event.key == pygame.K_x:
                if self.has_selection:
                    lo, hi = self.selection_range
                    try:
                        pygame.scrap.put_text(self.text[lo:hi])
                    except Exception as e:
                        cprint.warning("Clipboard cut failed:", e)
                    self._delete_selection()
                    self._notify_change()
                    self._ensure_cursor_visible()
                return True

            if event.key == pygame.K_RETURN:
                if self._on_submit_cb:
                    self._on_submit_cb(self.text)
                return True

            if event.key == pygame.K_ESCAPE:
                self.focused = False
                self._repeat_key = None
                return True

            # Tasti con repeat (frecce, backspace, delete)
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_HOME,
                             pygame.K_END, pygame.K_BACKSPACE, pygame.K_DELETE):
                self._process_key(event.key, mods)
                self._repeat_key = event.key
                self._repeat_mods = mods
                self._repeat_timer = 0.0
                return True

            # Testo normale (via event.unicode)
            if event.unicode and event.unicode.isprintable():
                self._insert_text(event.unicode)
                self._notify_change()
                self._ensure_cursor_visible()
                return True

        return False

    def update(self, dt: float):
        super().update(dt)
        if self.focused:
            self._cursor_timer += dt
            if self._cursor_timer >= self.CURSOR_BLINK_RATE:
                self._cursor_timer -= self.CURSOR_BLINK_RATE
                self._cursor_visible = not self._cursor_visible

            # Key repeat
            if self._repeat_key is not None:
                self._repeat_timer += dt
                if self._repeat_timer >= self.REPEAT_DELAY:
                    self._process_key(self._repeat_key, self._repeat_mods)
                    self._repeat_timer = self.REPEAT_DELAY - self.REPEAT_INTERVAL

    def _bg_color(self):
        if not self.enabled:
            c = self._bg_disabled or self.theme.bg_disabled
        elif self.focused:
            c = self._bg_hover or self.theme.bg_hover
        else:
            bg = self._bg or self.theme.bg
            bg_h = self._bg_hover or self.theme.bg_hover
            c = _lerp(bg, bg_h, self._hover_t)
        return (c[0], c[1], c[2], c[3] * self.alpha)

    def draw_bg(self, batch):
        if not self.visible:
            return
        th = self.theme

        bg = self._bg_color()
        batch.draw(self.x, self.y, self.w, self.h,
                   r=bg[0], g=bg[1], b=bg[2], a=bg[3])

        # Bordo inferiore accent quando focused
        if self.focused:
            ac = self._accent_color()
            batch.draw(self.x, self.y + self.h - 2, self.w, 2,
                       r=ac[0], g=ac[1], b=ac[2], a=self.alpha)

        # Selection highlight
        if self.focused and self.has_selection and self._font:
            lo, hi = self.selection_range
            sel_x1 = self._measure_to(lo) - self._scroll_x
            sel_x2 = self._measure_to(hi) - self._scroll_x
            vis_w = self._visible_width()
            # Clamp alla zona visibile
            sel_x1 = max(0.0, min(vis_w, sel_x1))
            sel_x2 = max(0.0, min(vis_w, sel_x2))
            if sel_x2 > sel_x1:
                sc = th.selection_color
                sel_h = self.scaled_font_size * 1.2
                batch.draw(self.x + self.theme.padding + sel_x1,
                           self.y + self.h / 2 - sel_h / 2,
                           sel_x2 - sel_x1, sel_h,
                           r=sc[0], g=sc[1], b=sc[2], a=sc[3] * self.alpha)

    def draw_bg_rounded(self, rr):
        if not self.visible:
            return
        th = self.theme

        bg = self._bg_color()
        rr.draw(self.x, self.y, self.w, self.h, th.border_radius,
                r=bg[0], g=bg[1], b=bg[2], a=bg[3])

        # Bordo inferiore accent quando focused
        if self.focused:
            ac = self._accent_color()
            rr.draw(self.x, self.y + self.h - 3, self.w, 3, th.border_radius * 0.5,
                    r=ac[0], g=ac[1], b=ac[2], a=self.alpha)

    def draw_bg_selection(self, batch):
        """Disegna selezione nel batch (chiamare dopo draw_bg_rounded se servono rounded+selezione)."""
        if not self.visible or not self.focused or not self.has_selection or not self._font:
            return
        th = self.theme
        lo, hi = self.selection_range
        sel_x1 = self._measure_to(lo) - self._scroll_x
        sel_x2 = self._measure_to(hi) - self._scroll_x
        vis_w = self._visible_width()
        sel_x1 = max(0.0, min(vis_w, sel_x1))
        sel_x2 = max(0.0, min(vis_w, sel_x2))
        if sel_x2 > sel_x1:
            sc = th.selection_color
            sel_h = self.scaled_font_size * 1.2
            batch.draw(self.x + self.theme.padding + sel_x1,
                       self.y + self.h / 2 - sel_h / 2,
                       sel_x2 - sel_x1, sel_h,
                       r=sc[0], g=sc[1], b=sc[2], a=sc[3] * self.alpha)

    def draw_text(self, font):
        if not self.visible:
            return
        th = self.theme

        # Salva riferimento font per misurazioni
        self._font = font

        text_y = self.y + self.h / 2
        text_x = self.x + self.theme.padding

        fs = self.scaled_font_size
        if not self.text and not self.focused:
            pc = th.placeholder_color
            font.draw(self.placeholder, text_x, text_y,
                      size=fs,
                      r=pc[0], g=pc[1], b=pc[2], a=pc[3] * self.alpha,
                      align_y="center")
            return

        self._ensure_cursor_visible()

        # Testo con offset di scroll
        if not self.enabled:
            clr = self._text_disabled or th.text_disabled
        else:
            clr = self._text_color or th.text

        # Disegna testo con offset scroll
        font.draw(self.text, text_x - self._scroll_x, text_y,
                  size=fs,
                  r=clr[0], g=clr[1], b=clr[2], a=self.alpha,
                  align_y="center")

        # Cursore
        if self.focused and self._cursor_visible:
            cursor_px = self._measure_to(self._cursor_pos) - self._scroll_x
            cc = th.cursor_color
            font.draw("|", text_x + cursor_px - 1, text_y,
                      size=fs,
                      r=cc[0], g=cc[1], b=cc[2], a=cc[3] * self.alpha,
                      align_y="center")
