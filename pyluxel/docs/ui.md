# UI Toolkit

Themeable widget system with buttons, toggles, sliders, text input, dropdowns, keyboard navigation, and layout containers. All coordinates in design space.

---

## Theme

Dataclass that controls the visual appearance of all widgets. Pass a custom `Theme` to any widget to override defaults.

```python
from pyluxel import Theme

# Default theme (neutral dark)
theme = Theme()

# Custom theme
theme = Theme(
    bg=(0.15, 0.15, 0.18, 0.9),
    bg_hover=(0.25, 0.25, 0.30, 0.95),
    bg_disabled=(0.10, 0.10, 0.12, 0.6),
    accent=(0.90, 0.30, 0.10),        # accent bar color (RGB)
    accent_width=3.0,
    accent_width_hover=6.0,
    text=(0.85, 0.85, 0.85),          # text color (RGB)
    text_hover=(1.0, 1.0, 1.0),
    text_disabled=(0.45, 0.45, 0.45),
    font_size=20.0,
    font_ref_height=48.0,          # widget height at which font_size is exact
    padding=12.0,
    border_radius=8.0,                # rounded corners (0 = sharp)
    anim_speed=10.0,                  # hover animation speed
    # Slider-specific
    track_color=(0.15, 0.15, 0.17, 1.0),
    track_height=4.0,
    handle_color=(0.20, 0.50, 1.0, 1.0),
    handle_size=16.0,
    # Toggle-specific
    toggle_off=(0.30, 0.30, 0.33, 1.0),
    toggle_on=(0.20, 0.50, 1.0, 1.0),
    # LineEdit-specific
    cursor_color=(0.85, 0.85, 0.85, 1.0),
    selection_color=(0.15, 0.40, 0.85, 0.45),
    placeholder_color=(0.45, 0.45, 0.48, 1.0),
)
```

---

## Widget (Base Class)

All widgets inherit from `Widget` and share these properties/methods.

### Common Properties

| Property | Type | Description |
|----------|------|-------------|
| `x, y` | `float` | Position (design space) |
| `w, h` | `float` | Size (design space) |
| `theme` | `Theme` | Visual theme |
| `visible` | `bool` | Whether the widget is drawn |
| `enabled` | `bool` | Whether the widget accepts input |
| `selected` | `bool` | External selection state (keyboard nav) |
| `alpha` | `float` | Global opacity (0.0 = invisible, 1.0 = fully opaque) |

### Common Methods

| Method | Description |
|--------|-------------|
| `set_position(x, y)` | Move widget |
| `set_size(w, h)` | Resize widget |
| `set_bg_color(bg, bg_hover, bg_disabled)` | Override background colors (RGBA tuples, hover/disabled optional) |
| `set_text_color(text, text_hover, text_disabled)` | Override text colors (RGB tuples, hover/disabled optional) |
| `set_accent_color(accent)` | Override accent color (RGB tuple) |
| `set_font_size(size)` | Set a fixed font size (overrides auto-scaling) |
| `show()` / `hide()` | Toggle visibility |
| `enable()` / `disable()` | Toggle interactivity |
| `is_hovered()` | True if mouse is over widget |
| `is_pressed()` | True if being clicked |
| `hit_test(mx, my)` | Point-in-rect test (design coords) |
| `handle_event(event)` | Process pygame event (returns True if consumed) |
| `update(dt)` | Update hover animation |
| `draw_bg(batch)` | Draw background with SpriteBatch |
| `draw_text(font)` | Draw text with SDFFont |

### Per-Widget Overrides

Any widget accepts optional overrides that take precedence over the Theme:

```python
btn = Button(100, 200, 200, 50, "Delete",
    theme=theme,
    bg=(0.5, 0.1, 0.1, 0.9),
    bg_hover=(0.7, 0.15, 0.15, 0.95),
    accent=(1.0, 0.2, 0.2),
    text_color=(1.0, 0.8, 0.8),
    font_size=28,              # fixed font size for this widget
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `bg` | `tuple \| None` | Background color (RGBA) |
| `bg_hover` | `tuple \| None` | Background color on hover (RGBA) |
| `bg_disabled` | `tuple \| None` | Background color when disabled (RGBA) |
| `accent` | `tuple \| None` | Accent bar color (RGB) |
| `text_color` | `tuple \| None` | Text color (RGB) |
| `text_hover` | `tuple \| None` | Text color on hover (RGB) |
| `text_disabled` | `tuple \| None` | Text color when disabled (RGB) |
| `font_size` | `float \| None` | Fixed font size (overrides auto-scaling) |

All default to `None` (use Theme values).

### Font Size Auto-Scaling

By default, the font size scales automatically based on the widget's height relative to `theme.font_ref_height` (default 48px):

```
scaled_font_size = theme.font_size * (widget.h / theme.font_ref_height)
```

- Widget with `h=48` (reference height): uses exactly `theme.font_size` (20px)
- Widget with `h=96`: font doubles to 40px
- Widget with `h=32`: font shrinks to ~13px

To override auto-scaling for a specific widget, pass `font_size=` in the constructor. To disable auto-scaling globally, set `font_ref_height` equal to the height of your widgets.

The property `widget.scaled_font_size` returns the effective font size (per-widget override if set, otherwise auto-scaled).

### Widget Alpha

Every widget has a global `alpha` property (0.0 - 1.0, default 1.0) that controls overall opacity. All backgrounds, accents, text, and sub-elements are multiplied by this value.

```python
widget.alpha = 0.5   # 50% transparent
widget.alpha = 0.0   # fully invisible (still processes events!)
widget.alpha = 1.0   # fully opaque (default)
```

Useful for fade-in/out effects:

```python
def update(self, dt):
    # Fade menu in
    self.menu_alpha = min(1.0, self.menu_alpha + dt * 2.0)
    for w in self.widgets:
        w.alpha = self.menu_alpha
        w.update(dt)
```

---

## Button

Clickable button with accent bar and centered text.

```python
from pyluxel import Button

def on_click():
    print("Clicked!")

btn = Button(
    x=100, y=200, w=200, h=50,
    label="Play",
    theme=theme,
    on_click=on_click,
    click_sound="click",     # optional SFX name (loaded via SoundManager)
    hover_sound="hover",     # optional hover SFX
    font_size=24,            # optional: override auto-scaled font size
)
```

---

## Toggle

On/off toggle switch with label and animated indicator.

```python
from pyluxel import Toggle

toggle = Toggle(
    x=100, y=300, w=250, h=45,
    label="Fullscreen",
    value=False,
    theme=theme,
    on_change=lambda val: print(f"Fullscreen: {val}"),
)

# Read/change state
toggle.value         # True/False
toggle.toggle()      # flip state
```

---

## Slider

Horizontal slider with label, value display, track, and draggable handle.

```python
from pyluxel import Slider

slider = Slider(
    x=100, y=400, w=300, h=60,
    label="Volume",
    value=0.8,
    min_val=0.0,
    max_val=1.0,
    step=0.05,           # 0 = continuous
    theme=theme,
    on_change=lambda val: print(f"Volume: {val:.2f}"),
)

# Read/change value
slider.value                    # current value
slider.set_range(0, 100)        # change min/max
slider.get_normalized_value()   # 0.0 - 1.0
slider.set_normalized_value(0.5)
slider.reset()                  # restore initial value
slider.is_dragging()            # True while being dragged
```

---

## LineEdit

Single-line text input with cursor, selection, clipboard, and auto-scroll.

```python
from pyluxel import LineEdit

edit = LineEdit(
    x=100, y=500, w=300, h=40,
    placeholder="Enter name...",
    text="",
    max_length=32,         # 0 = unlimited
    font=sdf_font,         # optional SDFFont for text measurements
    theme=theme,
    on_change=lambda text: print(f"Text: {text}"),
    on_submit=lambda text: print(f"Submitted: {text}"),
)

# Read/change text
edit.text              # current text
edit.clear()           # clear text
edit.select_all()      # select all
edit.focused           # True if focused
```

---

## Dropdown

Dropdown selection menu with overlay.

```python
from pyluxel import Dropdown

dropdown = Dropdown(
    x=100, y=600, w=250, h=45,
    label="Resolution",
    options=["1280x720", "1920x1080", "2560x1440"],
    selected=0,            # index of initial selection
    theme=theme,
    on_change=lambda idx: print(f"Selected: {idx}"),
)

# Read/change selection
dropdown.get_selected_index()    # current index
dropdown.set_selected_index(1)   # change selection
dropdown.selected_text()         # current option string
dropdown.get_options()           # list of option strings
dropdown.expanded                # True if dropdown is open
```

---

## FocusManager

Keyboard/gamepad navigation between widgets. When using `VBox(navigable=True)` or creating a `FocusManager` directly, default input bindings are applied automatically if not already bound:

| Action | Keyboard | Gamepad |
|--------|----------|---------|
| `nav_up` | Up arrow | DPAD Up |
| `nav_down` | Down arrow | DPAD Down |
| `nav_left` | Left arrow | DPAD Left |
| `nav_right` | Right arrow | DPAD Right |
| `confirm` | Enter, Space | A |
| `back` | Escape | B |

These defaults are **non-invasive** — if you've already called `Input.bind()` for any of these actions, your bindings are preserved. The auto-bind only fills in missing actions.

### Cross-axis navigation (`on_adjust`)

When a widget is focused and the user presses the cross-axis direction (e.g. left/right in a vertical layout), FocusManager calls `on_adjust(direction)` on the widget if available:

- **Slider**: left/right adjusts the value by `step` (or 5% of range if step is 0)
- **Toggle**: left/right toggles the value

```python
from pyluxel import FocusManager

focus = FocusManager()
focus.register(btn)
focus.register(toggle)
focus.register(slider)

# Process events (handles Tab, Shift+Tab, Enter)
for event in events:
    focus.handle_event(event)
    for widget in widgets:
        widget.handle_event(event)

# Manual control
focus.focus_next()
focus.focus_prev()
focus.get_focused()    # Widget or None
focus.clear()
```

---

## VBox / HBox

Layout containers that automatically arrange child widgets. Supports **nesting** — boxes can contain other boxes to build complex layouts.

### Equal Distribution (default)

When both dimensions are specified, children are **distributed equally** along the main axis:

```python
from pyluxel import VBox, HBox

# Vertical — children get equal height: (400 - padding*2 - spacing*(n-1)) / n
vbox = VBox(x=100, y=100, w=300, h=400, spacing=10)
vbox.add(btn)
vbox.add(toggle)
vbox.add(slider)
vbox.layout()

# Horizontal — children get equal width: (500 - padding*2 - spacing*(n-1)) / n
hbox = HBox(x=100, y=100, h=50, w=500, spacing=15)
hbox.add(btn1)
hbox.add(btn2)
hbox.layout()
```

### Pack Mode

Omit the main axis size to let children keep their own dimensions (total size is auto-calculated):

```python
# VBox without h — each child keeps its own height, total h is calculated
vbox = VBox(x=100, y=100, w=300)

# HBox without w — each child keeps its own width, total w is calculated
hbox = HBox(x=100, y=100, h=50)

# Or switch mode explicitly:
vbox.set_distribute(False)   # force pack even with fixed h
vbox.set_distribute(True)    # force equal distribution
```

### Nesting

```python
root = VBox(x=100, y=100, w=400, h=300)
row = HBox(0, 0, h=40, w=0)     # position/size set by parent during layout()
row.add(btn_save)
row.add(btn_cancel)
root.add(row)                     # nested HBox inside VBox
root.add(slider)
root.layout()                     # recursively lays out all children
```

### Anchor System

Position a box relative to screen edges without manual coordinate math. Anchoring is applied automatically at the end of `layout()`.

```python
# Center on screen
vbox.set_anchor(anchor_x="center", anchor_y="center")
vbox.layout()

# Bottom-right corner with 20px margin
vbox.set_anchor(anchor_x="right", anchor_y="bottom", margin=20)
vbox.layout()

# Top-left (default behavior)
vbox.set_anchor(anchor_x="left", anchor_y="top")
vbox.layout()
```

| Parameter | Values | Description |
|-----------|--------|-------------|
| `anchor_x` | `"left"` `"center"` `"right"` | Horizontal alignment |
| `anchor_y` | `"top"` `"center"` `"bottom"` | Vertical alignment |
| `margin` | `float` | Offset from edge (for left/right/top/bottom anchors) |

Coordinates are resolved against the design resolution (e.g. 1280x720).

### Management

```python
vbox.get_children()         # list of direct children
vbox.flat_widgets()         # all leaf widgets (recursively, skips nested boxes)
vbox.handle_events(events)  # dispatch events to children (recursive)
vbox.update(dt)             # update all children (recursive)
vbox.remove(btn)
vbox.clear()
```

---

## RoundedRectRenderer

GPU-accelerated rounded rectangle drawing. Pass it to `render_widgets()` for widgets with `border_radius > 0`.

```python
from pyluxel import RoundedRectRenderer

rounded = RoundedRectRenderer(ctx)

# Draw a single rounded rect
rounded.draw(x=100, y=100, w=200, h=50, radius=10,
             r=0.2, g=0.2, b=0.25, a=0.9)
```

---

## render_widgets()

Efficient batch rendering of a list of widgets. Handles backgrounds, rounded corners, text, and dropdown overlays in the correct order.

Accepts **VBox/HBox containers** directly — nested boxes are automatically flattened to their leaf widgets for rendering.

```python
from pyluxel import render_widgets, RoundedRectRenderer

rounded = RoundedRectRenderer(ctx)

# You can pass individual widgets, boxes, or a mix
render_widgets(
    widgets=[root_vbox, standalone_btn],  # boxes are expanded automatically
    batch=batch,
    white_tex=white_tex,
    font=sdf_font,        # SDFFont object or font name string
    rounded=rounded,       # None for sharp corners
)
```

---

## GlyphText

Renders mixed text and inline glyph textures using `{glyph_name}` syntax. Useful for controller button legends, key prompts, and any UI where icons appear inline with text.

```python
from pyluxel import GlyphText

gt = GlyphText(batch, font, textures, glyph_gap=2)
```

- `batch` — SpriteBatch
- `font` — SDFFont (or font name string, resolved via SDFFontCache)
- `textures` — TextureManager
- `glyph_gap` — pixels between consecutive glyphs (default 2)

### Syntax

- `{name}` — replaced by the texture loaded via `textures.get("name")`
- Consecutive `{a}{b}` — glyphs render touching (separated only by `glyph_gap`)
- Text before/after glyphs renders normally via SDFFont
- Glyph height matches font size; width preserves the texture aspect ratio

### draw()

```python
gt.draw(text, x, y, size=20, r=1.0, g=1.0, b=1.0, a=1.0,
        align_x="left", align_y="center")
```

- `align_x` — `"left"`, `"center"`, or `"right"`
- `align_y` — `"top"`, `"center"`, or `"bottom"`

### measure()

```python
w, h = gt.measure("Press {btn_a} to confirm", size=20)
```

Returns `(width, height)` of the full rendered string including glyphs.

### PlayStation Controller Glyphs

PyLuxel ships built-in PlayStation controller glyph textures in two styles: **basic** (flat icons) and **advanced** (outlined/colored).

Use the `GlyphText.ps()` factory to create a GlyphText with PS glyphs pre-loaded:

```python
gt = GlyphText.ps(batch, font, textures, style="basic")   # or "advanced"
gt.draw("{cross} Jump  {R3} Crouch  {L1}{R1} Switch", x, y, size=16)
```

Or load them manually into any TextureManager:

```python
from pyluxel import load_ps_glyphs

load_ps_glyphs(textures, style="advanced")
```

**Basic style** — `style="basic"`:

| Glyph name | File | Description |
|------------|------|-------------|
| `{cross}` | `cross.png` | Cross button |
| `{circle}` | `circle.png` | Circle button |
| `{square}` | `square.png` | Square button |
| `{triangle}` | `triangle.png` | Triangle button |
| `{dpad_up}` | `dpad_up.png` | D-pad up |
| `{dpad_down}` | `dpad_down.png` | D-pad down |
| `{dpad_left}` | `dpad_left.png` | D-pad left |
| `{dpad_right}` | `dpad_right.png` | D-pad right |
| `{L1}` | `l1.png` | Left shoulder |
| `{L2}` | `l2.png` | Left trigger |
| `{L3}` | `l3.png` | Left stick press |
| `{R1}` | `r1.png` | Right shoulder |
| `{R2}` | `r2.png` | Right trigger |
| `{R3}` | `r3.png` | Right stick press |
| `{share}` | `share.png` | Share button |
| `{options}` | `options.png` | Options button |

**Advanced style** — `style="advanced"`:

| Glyph name | File | Description |
|------------|------|-------------|
| `{cross}` | `outline-blue-cross.png` | Cross (blue outline) |
| `{circle}` | `outline-red-circle.png` | Circle (red outline) |
| `{square}` | `outline-purple-square.png` | Square (purple outline) |
| `{triangle}` | `outline-green-triangle.png` | Triangle (green outline) |
| `{dpad_up}` | `outline-top.png` | D-pad up |
| `{dpad_down}` | `outline-bottom.png` | D-pad down |
| `{dpad_left}` | `outline-left.png` | D-pad left |
| `{dpad_right}` | `outline-right.png` | D-pad right |
| `{L1}` | `plain-rectangle-L1.png` | Left shoulder |
| `{L2}` | `plain-rectangle-L2.png` | Left trigger |
| `{L3}` | `press-L.png` | Left stick press |
| `{R1}` | `plain-rectangle-R1.png` | Right shoulder |
| `{R2}` | `plain-rectangle-R2.png` | Right trigger |
| `{R3}` | `press-R.png` | Right stick press |
| `{left_stick}` | `direction-L.png` | Left analog stick |
| `{right_stick}` | `direction-R.png` | Right analog stick |
| `{share}` | `outline-share.png` | Share button |
| `{options}` | `plain-small-option.png` | Options button |
| `{ps}` | `plain-big-PS.png` | PlayStation button |

### Example

```python
from pyluxel import App, GlyphText, Input
import pygame

class MyGame(App):
    def setup(self):
        Input.bind("quit", pygame.K_ESCAPE)
        self.gt = GlyphText.ps(self.batch, self.get_font(), self.textures, style="basic")

    def update(self, dt):
        if Input.pressed("quit"):
            self.quit()

    def draw(self):
        pass

    def draw_overlay(self):
        self.gt.draw("{cross} Confirm   {circle} Back   {dpad_left}{dpad_right} Move",
                     640, 680, size=16, a=0.8, align_x="center")

MyGame(1280, 720, "Glyph Demo").run()
```

---

## Complete Example

```python
from pyluxel import App, Input, Theme, Button, Slider, Toggle, VBox, render_widgets, RoundedRectRenderer
import pygame

class SettingsMenu(App):
    def setup(self):
        Input.bind("quit", pygame.K_ESCAPE)

        self.theme = Theme(border_radius=8)
        self.rounded = RoundedRectRenderer(self.ctx)

        self.volume = Slider(0, 0, 300, 60, "Volume", value=0.8,
                             theme=self.theme, on_change=lambda v: Sound.set_master_volume(v))
        self.fullscreen = Toggle(0, 0, 300, 45, "Fullscreen",
                                 theme=self.theme, on_change=lambda v: self.set_fullscreen(v))
        self.back_btn = Button(0, 0, 300, 50, "Back",
                               theme=self.theme, on_click=self.quit)

        self.layout = VBox(x=490, y=200, w=300, spacing=10)
        self.layout.add(self.volume)
        self.layout.add(self.fullscreen)
        self.layout.add(self.back_btn)
        self.layout.layout()

        self.widgets = [self.volume, self.fullscreen, self.back_btn]

    def update(self, dt):
        if Input.pressed("quit"):
            self.quit()
        for w in self.widgets:
            w.update(dt)

    def draw(self):
        pass

    def handle_event(self, event):
        for w in self.widgets:
            w.handle_event(event)

    def draw_overlay(self):
        render_widgets(self.widgets, self.batch, self.white_tex,
                       self.get_font(), self.rounded)

SettingsMenu(1280, 720, "Settings").run()
```
