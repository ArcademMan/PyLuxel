from pyluxel.core.resolution import Resolution
from pyluxel.ui.focus import FocusManager

_R = Resolution()


class _BoxBase:
    """Base per VBox e HBox."""

    visible = True

    def __init__(self, x, y, spacing=10, padding=12, navigable=False):
        self.x = x
        self.y = y
        self.spacing = spacing
        self.padding = padding
        self._children = []
        self._focus = None
        self._navigable = navigable
        self._controller_navigable = navigable
        self._distribute = True
        self._anchor_x = None
        self._anchor_y = None
        self._margin = 0

    def set_controller_navigable(self, enabled: bool):
        """Abilita/disabilita navigazione via controller (DPAD/bottoni)."""
        self._controller_navigable = enabled
        if self._focus:
            self._focus.controller_navigable = enabled

    def set_distribute(self, enabled: bool):
        """Abilita/disabilita la distribuzione equa dello spazio tra i figli."""
        self._distribute = enabled

    def set_anchor(self, anchor_x: str = "left", anchor_y: str = "top", margin: float = 0):
        """Position the box relative to screen edges.

        anchor_x: "left" | "center" | "right"
        anchor_y: "top" | "center" | "bottom"
        margin: offset from screen edge (used for left/right/top/bottom)
        """
        self._anchor_x = anchor_x
        self._anchor_y = anchor_y
        self._margin = margin

    def _apply_anchor(self):
        """Recalculate x/y based on anchor settings after layout sizes are known."""
        if self._anchor_x is None and self._anchor_y is None:
            return
        bw = _R.BASE_WIDTH
        bh = _R.BASE_HEIGHT
        w = self.w
        h = self.h

        old_x, old_y = self.x, self.y

        ax = self._anchor_x or "left"
        ay = self._anchor_y or "top"

        if ax == "center":
            self.x = (bw - w) / 2
        elif ax == "right":
            self.x = bw - w - self._margin
        else:
            self.x = self._margin if self._margin else self.x

        if ay == "center":
            self.y = (bh - h) / 2
        elif ay == "bottom":
            self.y = bh - h - self._margin
        else:
            self.y = self._margin if self._margin else self.y

        # Shift all children by the delta
        dx = self.x - old_x
        dy = self.y - old_y
        if dx != 0 or dy != 0:
            self._shift_children(dx, dy)

    def _shift_children(self, dx, dy):
        """Shift all children positions by (dx, dy)."""
        for child in self._children:
            child.x += dx
            child.y += dy
            if isinstance(child, _BoxBase):
                child._shift_children(dx, dy)

    def add(self, widget):
        self._children.append(widget)
        return widget

    def insert(self, widget, index: int):
        """Inserisce un widget alla posizione specificata."""
        self._children.insert(index, widget)
        return widget

    def contains(self, widget) -> bool:
        """True se il widget e' nel layout."""
        return widget in self._children

    def remove(self, widget):
        self._children.remove(widget)
        if self._focus:
            self._focus.widgets = self._children

    def clear_focus(self):
        """Deseleziona il widget corrente. Si riattiva al prossimo input."""
        if self._focus:
            self._focus.clear_focus()

    def clear(self):
        self._children.clear()
        if self._focus:
            self._focus.widgets = []

    @property
    def children(self):
        return self._children

    def get_children(self) -> list:
        """Restituisce la lista dei widget figli."""
        return self._children

    def flat_widgets(self) -> list:
        """Raccoglie ricorsivamente tutti i widget foglia (non-box)."""
        result = []
        for child in self._children:
            if isinstance(child, _BoxBase):
                result.extend(child.flat_widgets())
            else:
                result.append(child)
        return result

    def handle_events(self, events):
        if self._focus:
            for event in events:
                self._focus.handle_event(event)
        else:
            for event in events:
                for w in self._children:
                    if isinstance(w, _BoxBase):
                        w.handle_events([event])
                    else:
                        w.handle_event(event)

    def update(self, dt):
        if self._focus:
            self._focus.update(dt)
        else:
            for w in self._children:
                if isinstance(w, _BoxBase):
                    w.update(dt)
                else:
                    w.update(dt)


class VBox(_BoxBase):
    """Impila widget verticalmente. w obbligatorio (children si allargano).

    Se h e' specificato, lo spazio viene distribuito equamente tra i figli.
    Senza h, l'altezza totale viene calcolata dalle dimensioni dei figli (pack).
    """

    def __init__(self, x, y, w, h=None, spacing=10, padding=12, navigable=False):
        super().__init__(x, y, spacing, padding, navigable)
        self.w = w
        self._h = h or 0.0
        self._fixed_h = h is not None

    @property
    def h(self):
        return self._h

    @h.setter
    def h(self, value):
        self._h = value
        self._fixed_h = True

    def layout(self):
        pad = self.padding
        n = len(self._children)
        child_w = self.w - pad * 2

        # Distribuzione equa quando h e' fissato e distribute e' attivo
        if self._fixed_h and self._distribute and n > 0:
            avail = self._h - pad * 2 - self.spacing * (n - 1)
            child_h = avail / n
            cursor_y = self.y + pad
            for child in self._children:
                child.x = self.x + pad
                child.w = child_w
                child.y = cursor_y
                child.h = child_h
                if isinstance(child, _BoxBase):
                    child.layout()
                cursor_y += child_h + self.spacing
        else:
            # Pack: ogni figlio mantiene la sua h
            cursor_y = self.y + pad
            for child in self._children:
                child.x = self.x + pad
                child.w = child_w
                child.y = cursor_y
                if isinstance(child, _BoxBase):
                    child.layout()
                cursor_y += child.h + self.spacing
            if n > 0:
                self._h = pad * 2 + sum(c.h for c in self._children) + self.spacing * (n - 1)
            else:
                self._h = pad * 2

        if self._navigable:
            self._focus = FocusManager(self.flat_widgets(), wrap=True, axis="vertical",
                                       controller_navigable=self._controller_navigable)

        self._apply_anchor()


class HBox(_BoxBase):
    """Impila widget orizzontalmente. h obbligatorio (children si allungano).

    Se w e' specificato, lo spazio viene distribuito equamente tra i figli.
    Senza w, la larghezza totale viene calcolata dalle dimensioni dei figli (pack).
    """

    def __init__(self, x, y, h, w=None, spacing=10, padding=12, navigable=False):
        super().__init__(x, y, spacing, padding, navigable)
        self.h = h
        self._w = w or 0.0
        self._fixed_w = w is not None

    @property
    def w(self):
        return self._w

    @w.setter
    def w(self, value):
        self._w = value
        self._fixed_w = True

    def layout(self):
        pad = self.padding
        n = len(self._children)
        child_h = self.h - pad * 2

        # Distribuzione equa quando w e' fissato e distribute e' attivo
        if self._fixed_w and self._distribute and n > 0:
            avail = self._w - pad * 2 - self.spacing * (n - 1)
            child_w = avail / n
            cursor_x = self.x + pad
            for child in self._children:
                child.y = self.y + pad
                child.h = child_h
                child.x = cursor_x
                child.w = child_w
                if isinstance(child, _BoxBase):
                    child.layout()
                cursor_x += child_w + self.spacing
        else:
            # Pack: ogni figlio mantiene la sua w
            cursor_x = self.x + pad
            for child in self._children:
                child.y = self.y + pad
                child.h = child_h
                child.x = cursor_x
                if isinstance(child, _BoxBase):
                    child.layout()
                cursor_x += child.w + self.spacing
            if n > 0:
                self._w = pad * 2 + sum(c.w for c in self._children) + self.spacing * (n - 1)
            else:
                self._w = pad * 2

        if self._navigable:
            self._focus = FocusManager(self.flat_widgets(), wrap=True, axis="horizontal",
                                       controller_navigable=self._controller_navigable)

        self._apply_anchor()
