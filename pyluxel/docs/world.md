# World

Tilemap system for grid-based worlds and parallax backgrounds for scrolling layers.

---

## Tileset

A spritesheet divided into fixed-size tiles. Given a global tile ID (GID), returns UV coordinates for the SpriteBatch.

```python
from pyluxel import Tileset

tileset = Tileset(
    texture=tileset_texture,    # ModernGL texture
    tile_width=16,
    tile_height=16,
    first_gid=1,                # global ID of the first tile (Tiled convention)
)

# Properties
tileset.columns          # tiles per row
tileset.rows             # tile rows
tileset.tile_count       # total tiles

# UV lookup
tileset.contains_gid(5)          # True if this tileset has GID 5
u0, v0, u1, v1 = tileset.get_uvs(5)  # UV coords for GID 5
```

---

## TileLayer

A 2D grid of tile IDs. Tile ID 0 = empty cell (not drawn). Supports camera culling for efficient rendering.

```python
from pyluxel import TileLayer

layer = TileLayer(
    name="ground",
    width=100,          # grid width in tiles
    height=50,          # grid height in tiles
    tile_width=16,
    tile_height=16,
    data=None,          # 2D list or None (filled with 0s)
)

# Read/write tiles
layer.get(tx=5, ty=3)              # tile ID at grid position (0 if out of bounds)
layer.set(tx=5, ty=3, tile_id=42)

# Fill operations
layer.clear()                       # all cells to 0
layer.fill(tile_id=1)              # fill entire layer
layer.fill_rect(10, 5, 20, 10, tile_id=3)  # fill rectangular area

# Collision
layer.is_solid(tx=5, ty=3)        # True if tile_id != 0

# Coordinate conversion
tx, ty = layer.world_to_tile(160.0, 80.0)
wx, wy = layer.tile_to_world(10, 5)

# Properties
layer.visible = True
layer.opacity = 0.8
layer.name                          # "ground"
layer.width, layer.height          # grid dimensions

# Rendering (with camera culling)
batch.begin(tileset.texture)
layer.render(batch, tileset, camera, screen_w=1280, screen_h=720)
batch.end()
```

---

## TileMap

Container for a complete map: tilesets, layers, and objects.

```python
from pyluxel import TileMap

tilemap = TileMap(
    width=100,          # map width in tiles
    height=50,          # map height in tiles
    tile_width=16,
    tile_height=16,
)

# Dimensions
tilemap.pixel_width         # width * tile_width
tilemap.pixel_height        # height * tile_height

# Layers
tilemap.add_layer(ground_layer)
tilemap.get_layer("ground")        # TileLayer or None
tilemap.remove_layer("ground")     # True if found

# Tilesets
tilemap.tilesets                    # list of Tileset
tilemap.get_tileset_for_gid(5)     # Tileset containing GID 5

# Objects
tilemap.add_object(spawn_point)
tilemap.get_objects()               # all objects
tilemap.get_objects(type="spawn")   # filtered by type
tilemap.remove_object(obj)
tilemap.clear_objects()
```

---

## MapObject

A positioned object on the map (spawn points, triggers, collision shapes). Dataclass.

```python
from pyluxel import MapObject

obj = MapObject(
    name="player_spawn",
    type="spawn",
    x=320.0,
    y=480.0,
    width=32.0,
    height=32.0,
    properties={"direction": "right"},
    polygon=None,     # optional list of (x, y) tuples for polygon shapes
)
```

---

## load_map()

Load a map from a JSON file. Supports Tiled JSON format (orthogonal maps with tile layers and object groups).

```python
from pyluxel import load_map

# Load with textures
tilemap = load_map("assets/maps/level1.json", texture_manager=textures)

# Load objects-only map (no tileset textures needed)
tilemap = load_map("assets/maps/triggers.json", texture_manager=None)
```

Tileset image paths in the JSON are resolved by filename only (the `TextureManager` loads them from its `base_path`). This handles Tiled's absolute path exports automatically.

### Rendering a Complete Map

```python
# Load
tilemap = load_map("assets/maps/level1.json", textures)

# Get layers
ground = tilemap.get_layer("ground")
walls = tilemap.get_layer("walls")

# Get spawn points
spawns = tilemap.get_objects(type="spawn")
for obj in spawns:
    print(f"Spawn at ({obj.x}, {obj.y})")

# Render (during scene pass)
for layer in tilemap.layers:
    ts = tilemap.get_tileset_for_gid(layer.get(0, 0)) or tilemap.tilesets[0]
    batch.begin(ts.texture)
    layer.render(batch, ts, camera, 1280, 720)
    batch.end()

# Camera bounds
camera.update(player_x, player_y,
              tilemap.pixel_width, tilemap.pixel_height, dt)
```

---

## ParallaxBackground

Stack of scrolling background layers with different scroll speeds for depth perception.

```python
from pyluxel import ParallaxBackground

bg = ParallaxBackground()

# Add layers (drawn in order, first = farthest)
bg.add(sky_tex, scroll_speed=0.0)           # fixed background
bg.add(mountains_tex, scroll_speed=0.2)     # slow scroll
bg.add(trees_tex, scroll_speed=0.5)         # medium scroll
bg.add(bushes_tex, scroll_speed=0.8)        # fast scroll
```

### ParallaxLayer

Each layer returned by `add()` can be configured:

```python
layer = bg.add(
    texture=mountains_tex,
    scroll_speed=0.3,       # 0=fixed, 0.5=half camera speed, 1=follows camera
    repeat_x=True,          # tile horizontally
    repeat_y=False,         # tile vertically
    offset_y=0.0,           # vertical offset
)

# Properties
layer.texture
layer.scroll_speed
layer.repeat_x, layer.repeat_y
layer.offset_y
layer.tex_width, layer.tex_height
```

### Rendering

```python
# Render during scene pass (before tilemap)
bg.render(batch, camera_x=camera.x, camera_y=camera.y,
          screen_w=1280, screen_h=720)
```

### Management

```python
bg.layer_count        # number of layers
bg.remove(layer)      # remove a specific layer
bg.clear()            # remove all layers
```
