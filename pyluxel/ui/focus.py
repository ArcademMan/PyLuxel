import pygame

from pyluxel.input import Input

_ui_bindings_applied = False


def _ensure_ui_bindings():
    global _ui_bindings_applied
    if _ui_bindings_applied:
        return
    _ui_bindings_applied = True
    from pyluxel.input import Pad
    if not Input.is_bound("nav_up"):
        Input.bind("nav_up", pygame.K_UP, Pad.DPAD_UP)
    if not Input.is_bound("nav_down"):
        Input.bind("nav_down", pygame.K_DOWN, Pad.DPAD_DOWN)
    if not Input.is_bound("nav_left"):
        Input.bind("nav_left", pygame.K_LEFT, Pad.DPAD_LEFT)
    if not Input.is_bound("nav_right"):
        Input.bind("nav_right", pygame.K_RIGHT, Pad.DPAD_RIGHT)
    if not Input.is_bound("confirm"):
        Input.bind("confirm", pygame.K_RETURN, pygame.K_SPACE, Pad.A)
    if not Input.is_bound("back"):
        Input.bind("back", pygame.K_ESCAPE, Pad.B)


class FocusManager:
    """Gestisce navigazione su una lista di widget via InputManager.

    Mouse events restano event-based (handle_event).
    Navigazione tastiera/controller via InputManager (update).
    Quando il widget corrente ha focused=True (es. LineEdit), gli eventi
    raw vengono passati direttamente al widget (serve event.unicode).
    """

    def __init__(self, widgets=None, wrap=True, axis="vertical", controller_navigable=True):
        _ensure_ui_bindings()
        self._widgets = list(widgets) if widgets else []
        self.wrap = wrap
        self.axis = axis  # "vertical" -> nav_up/nav_down, "horizontal" -> nav_left/nav_right
        self.controller_navigable = controller_navigable
        self._index = 0

    @property
    def widgets(self):
        return self._widgets

    @widgets.setter
    def widgets(self, value):
        self._widgets = list(value)
        self._index = 0

    @property
    def index(self):
        return self._index

    def current(self):
        """Ritorna il widget attualmente selezionato, o None."""
        if self._widgets and 0 <= self._index < len(self._widgets):
            return self._widgets[self._index]
        return None

    def next(self):
        """Sposta il focus al widget successivo."""
        self._move(1)

    def prev(self):
        """Sposta il focus al widget precedente."""
        self._move(-1)

    def clear(self):
        """Rimuove tutti i widget e resetta l'indice."""
        self._widgets.clear()
        self._index = 0

    def clear_focus(self):
        """Deseleziona il widget corrente senza rimuovere la lista."""
        for w in self._widgets:
            w.selected = False
        self._index = -1

    def focus_widget(self, widget) -> bool:
        """Imposta il focus su un widget specifico. Ritorna True se trovato."""
        for i, w in enumerate(self._widgets):
            if w is widget:
                self._index = i
                return True
        return False

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Gestisce solo mouse events + forwarding a widget focused."""
        if not self._widgets:
            return False

        current = self._widgets[self._index]

        # Widget con focus (LineEdit editing, Dropdown espanso)
        # riceve TUTTI gli eventi raw (serve event.unicode per testo)
        if getattr(current, 'focused', False):
            return current.handle_event(event)

        # Mouse events: delega a tutti i children
        if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN,
                          pygame.MOUSEBUTTONUP):
            consumed = False
            for w in self._widgets:
                if w.handle_event(event):
                    consumed = True
            return consumed

        return False

    def _nav_pressed(self, action):
        """Input.pressed filtrato: ignora controller se controller_navigable=False."""
        if not Input.pressed(action):
            return False
        if self.controller_navigable:
            return True
        # Verifica che almeno un trigger keyboard sia attivo
        keys = pygame.key.get_pressed()
        from pyluxel.input.manager import _PadTrigger, _PadAxisTrigger
        for trigger in Input.get_bindings(action):
            if isinstance(trigger, int) and keys[trigger]:
                return True
        return False

    def _move(self, direction):
        n = len(self._widgets)
        if n == 0:
            return
        new = self._index + direction
        if self.wrap:
            new %= n
        else:
            new = max(0, min(n - 1, new))
        self._index = new

    def update(self, dt):
        if not self._widgets:
            return

        # Nessun focus attivo (dopo clear_focus) — riattiva al primo input
        if self._index < 0:
            for action in ("nav_up", "nav_down", "nav_left", "nav_right", "confirm"):
                if self._nav_pressed(action):
                    self._index = 0
                    break
            # Sync mouse hover anche senza focus
            for i, w in enumerate(self._widgets):
                if w._hovered:
                    self._index = i
                    break
            if self._index < 0:
                for w in self._widgets:
                    w.selected = False
                    w.update(dt)
                return

        current = self._widgets[self._index]

        # Navigazione via InputManager (skip se widget ha focus override)
        if not getattr(current, 'focused', False):
            # Asse principale
            if self.axis == "vertical":
                if self._nav_pressed("nav_up"):
                    self._move(-1)
                elif self._nav_pressed("nav_down"):
                    self._move(1)
            else:
                if self._nav_pressed("nav_left"):
                    self._move(-1)
                elif self._nav_pressed("nav_right"):
                    self._move(1)

            # Cross-axis: on_adjust se disponibile
            cb = getattr(current, 'on_adjust', None)
            if cb:
                if self.axis == "vertical":
                    if self._nav_pressed("nav_right"):
                        cb(1)
                    elif self._nav_pressed("nav_left"):
                        cb(-1)
                else:
                    if self._nav_pressed("nav_down"):
                        cb(1)
                    elif self._nav_pressed("nav_up"):
                        cb(-1)

            # Confirm
            if self._nav_pressed("confirm"):
                current._on_click()

        # Sync mouse hover -> indice focus
        for i, w in enumerate(self._widgets):
            if w._hovered:
                self._index = i
                break

        # Imposta selected su widget corrente
        for i, w in enumerate(self._widgets):
            w.selected = (i == self._index)
            w.update(dt)
