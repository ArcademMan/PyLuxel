# Text Rendering

Two text rendering backends: SDF (scalable) and Bitmap (per-size atlas), plus a FontManager singleton for loading TTF files.

---

## FontManager

Singleton that loads and caches pygame font objects from `.ttf` files. Provides semantic names for font families.

```python
from pyluxel import FontManager

# Configure at startup
FontManager.init("assets/fonts", font_files={
    "body": "Inter-Regular.ttf",
    "body_bold": "Inter-Bold.ttf",
    "title": "Inter-Bold.ttf",
})

# Get a pygame.font.Font at a specific size
fm = FontManager()
title_font = fm.get(FontManager.TITLE, 48)
body_font = fm.get(FontManager.BODY, 16)

# Register additional fonts at runtime
fm.register("mono", "JetBrainsMono.ttf")

# Clear cache after resolution change
fm.clear_cache()
```

### Built-in Name Constants

| Constant | Value |
|----------|-------|
| `FontManager.BODY` | `"body"` |
| `FontManager.BODY_BOLD` | `"body_bold"` |
| `FontManager.TITLE` | `"title"` |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `init(fonts_dir, font_files=None)` | `FontManager` | Configure fonts directory and mapping |
| `get(name, size)` | `pygame.font.Font` | Get cached font (creates if needed) |
| `register(name, filename)` | `None` | Add a new font name → file mapping |
| `clear_cache()` | `None` | Invalidate all cached fonts |
| `list_registered_fonts()` | `list[str]` | List registered font names |
| `is_font_registered(name)` | `bool` | Check if a font name is registered |

---

## SDFFont

Signed Distance Field font rendering. The atlas is generated once (slow on first launch), cached to disk as a binary `.dat` file, and rendered via a GPU shader. Scales to any size without quality loss.

```python
from pyluxel import SDFFont, SDFFontCache, FontManager

# Option 1: Use SDFFontCache (recommended)
cache = SDFFontCache(ctx, renderer.sdf_prog, cache_dir="assets/cache/sdf")
font = cache.get(FontManager.BODY)

# Option 2: Create directly
font = SDFFont(ctx, renderer.sdf_prog, font_name="body", cache_dir="sdf_cache")
```

### Drawing Text

```python
# Draw text (batched, call flush() when done)
font.draw(
    text="Hello World",
    x=100, y=200,
    size=32,                  # desired size in design pixels
    r=1.0, g=1.0, b=1.0, a=1.0,
    align_x="left",           # "left", "center", "right"
    align_y="top",             # "top", "center", "bottom"
)

# Multiline text — use \n to break lines
font.draw("Line 1\nLine 2\nLine 3", 100, 200, size=24)

# IMPORTANT: flush after all draw calls
font.flush()

# Measure text without drawing (multiline: returns widest line, total height)
width, height = font.measure("Hello World", size=32)
```

### Vertical Centering

When `align_y="center"`, the text is centered using the **cap-height** (height of uppercase letters like H) rather than the full glyph bounding box. This ensures that uppercase text and text without descenders (g, p, q, y) appears visually centered — for example inside buttons.

### SDFFont Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `draw(text, x, y, size, r, g, b, a, align_x, align_y)` | `None` | Queue text for rendering |
| `flush()` | `None` | Send queued text to GPU |
| `measure(text, size)` | `(float, float)` | Measure text (width, height) |
| `get_glyph_width(char, size)` | `float` | Width of a single glyph |
| `get_line_height(size)` | `float` | Line height at given size |
| `has_char(char)` | `bool` | Whether character is in the atlas |
| `release()` | `None` | Free GPU resources |

### SDFFontCache

One SDFFont per font family. Since SDF fonts scale via shader, you only need one atlas per family.

```python
cache = SDFFontCache(ctx, renderer.sdf_prog, cache_dir="assets/cache/sdf")

font = cache.get("body")         # creates or returns cached SDFFont
font = cache.get("title")        # different family = different atlas

cache.list_cached_fonts()        # ["body", "title"]
cache.clear()                    # release all atlases
cache.release()                  # alias for clear()

# Singleton access (after creating at least one instance)
SDFFontCache.instance().get("body")
```

---

## BitmapFont

Rasterized font with a per-size texture atlas. Uses 2x oversampling with LINEAR filtering for clean anti-aliasing. Best for fixed-size text that doesn't need scaling.

```python
from pyluxel import BitmapFont, FontCache, FontManager

# Option 1: Use FontCache (recommended)
font_cache = FontCache(ctx, renderer.sprite_prog)
font = font_cache.get(FontManager.BODY, size=24)

# Option 2: Create directly
pg_font = FontManager().get("body", 24)
font = BitmapFont(ctx, renderer.sprite_prog, pg_font, requested_size=24)
```

### Drawing Text

```python
# BitmapFont uses the SpriteBatch for rendering
batch.begin(font.atlas)
font.draw(
    batch=batch,
    text="Score: 100",
    x=10, y=10,
    r=1.0, g=1.0, b=1.0, a=1.0,
    align_x="left",           # "left", "center", "right"
    align_y="top",             # "top", "center", "bottom"
)
batch.end()

# Measure text
width, height = font.measure("Score: 100")
```

### BitmapFont Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `draw(batch, text, x, y, r, g, b, a, align_x, align_y)` | `None` | Draw text using SpriteBatch |
| `measure(text)` | `(float, float)` | Measure text (width, height) |
| `get_glyph_width(char)` | `float` | Width of a single glyph |
| `get_line_height()` | `float` | Line height |
| `has_char(char)` | `bool` | Whether character is in atlas |
| `release()` | `None` | Free atlas texture |

### FontCache

Caches BitmapFont instances per font+size combination. Each combination creates a separate texture atlas.

```python
font_cache = FontCache(ctx, renderer.sprite_prog)

small = font_cache.get("body", 16)
large = font_cache.get("body", 32)   # separate atlas

font_cache.list_cached_fonts()       # [("body", 16), ("body", 32)]
font_cache.clear()                   # release all atlases
```

---

## SDF vs Bitmap: When to Use What

| Feature | SDFFont | BitmapFont |
|---------|---------|------------|
| Scales to any size | Yes (via shader) | No (one atlas per size) |
| First-launch cost | Slow (generates SDF atlas) | Fast |
| VRAM per family | One atlas for all sizes | One atlas per size |
| Anti-aliasing | SDF shader (crisp at any scale) | 2x oversampled + LINEAR |
| Best for | UI text, HUD, dynamic sizes | Fixed-size labels, pixel art |
| Rendering | Own shader + flush() | Uses SpriteBatch |
