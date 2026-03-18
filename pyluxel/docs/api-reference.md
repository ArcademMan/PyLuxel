# API Reference

Quick reference for all public PyLuxel classes, functions, and constants. For detailed explanations and examples, see the topic docs.

---

## Core

### Resolution (singleton)

```python
R = Resolution()
R.init(design_w, design_h)
R.set_resolution(screen_w, screen_h)
R.s(value) -> float                  # scale value to screen space
R.sf() -> float                      # scale factor
R.unscale(screen_val) -> float       # screen → design
R.design_width -> int
R.design_height -> int
R.screen_width -> int
R.screen_height -> int
```

### Renderer

```python
Renderer(ctx, screen_w, screen_h, design_width, design_height, clear_color)
renderer.begin_scene()
renderer.begin_shadow_casters()
renderer.begin_normal()
renderer.begin_lights()
renderer.combine(ambient=0.15)
renderer.post_process(fx: PostFX)
renderer.begin_screen_overlay()
renderer.resize(w, h)
renderer.screenshot() -> bytes
renderer.release()
renderer.projection -> np.ndarray
renderer.screen_width -> int
renderer.screen_height -> int
renderer.design_width -> int
renderer.design_height -> int
renderer.sprite_prog -> moderngl.Program
renderer.light_prog -> moderngl.Program
renderer.sdf_prog -> moderngl.Program
renderer.combine_texture -> moderngl.Texture
renderer.shockwaves -> ShockwaveManager
renderer.heat_hazes -> HeatHazeManager
```

### SpriteBatch

```python
SpriteBatch(ctx, program, max_sprites=4096)
batch.begin(texture)
batch.draw(x, y, w, h, u0=0, v0=0, u1=1, v1=1, r=1, g=1, b=1, a=1, angle=0)
batch.flush()
batch.end()
```

### TextureManager

```python
TextureManager(ctx, base_path="assets")
textures.load(name, filename=None, nearest=False) -> moderngl.Texture
textures.surface_to_texture(surface, nearest=False) -> moderngl.Texture
textures.create_from_color(w, h, r=255, g=255, b=255, a=255) -> moderngl.Texture
textures.get(name) -> moderngl.Texture | None
textures.reload(name) -> moderngl.Texture
textures.release(name)
textures.release_all()
textures.is_loaded(name) -> bool
textures.get_loaded_names() -> list[str]
textures.get_texture_size(name) -> tuple[int, int]
```

### Camera

```python
Camera(x=0, y=0, smoothing=5.0)
camera.update(target_x, target_y, world_w, world_h, dt, margin_x=0, margin_y=0)
camera.apply(batch, renderer)
camera.screen_to_world(sx, sy) -> tuple[float, float]
camera.shake(intensity=5.0, duration=0.3)
camera.get_bounds(screen_w, screen_h) -> tuple[float, float, float, float]
camera.set_zoom(zoom)              # 1.0 = default, >1 = zoom in, <1 = zoom out
camera.get_zoom() -> float
camera.x -> float
camera.y -> float
camera.smoothing -> float

# GPU camera (pass to begin_scene for automatic zoom)
renderer.begin_scene(camera)       # all draw calls in world space, zoom automatic
renderer.apply_camera(camera)      # apply mid-frame
renderer.reset_camera()            # reset to design space
```

### PostFX (dataclass)

```python
PostFX(
    bloom=0.0, vignette=0.0, tone_mapping="aces",
    exposure=1.0, chromatic_aberration=0.0, film_grain=0.0,
    god_rays=0.0, god_rays_x=0.5, god_rays_y=0.0,
    god_rays_decay=0.96, god_rays_density=0.5,
    pixel_perfect=False,
)

fx.set_pixel_perfect(enabled: bool)
# NEAREST filtering (pixel art nitido) o LINEAR (smooth).
# Influenza solo la scena (combine FBO -> screen).
# L'HUD (begin_screen_overlay) non e' influenzato.
```

### Shockwave / ShockwaveManager

```python
Shockwave(x, y, max_radius=200, thickness=30, strength=0.05)
ShockwaveManager(max_shockwaves=8)
manager.add(x, y, max_radius, thickness, strength) -> Shockwave
manager.update(dt)
manager.clear()
```

### HeatHaze / HeatHazeManager

```python
HeatHaze(x, y, width, height, strength=0.003, speed=3.0, scale=20.0)
HeatHazeManager(max_hazes=4)
manager.add(x, y, w, h, strength, speed, scale) -> HeatHaze
manager.remove(haze)
manager.clear()
```

---

## Effects

### Light

```python
Light(x, y, radius, color=(1,1,1), intensity=1.0,
      falloff=FalloffMode.QUADRATIC, is_spotlight=False,
      direction=0.0, angle=45.0,
      flicker_speed=0.0, flicker_amount=0.0, flicker_style="smooth",
      z=70.0,
      cast_shadows=False, shadow_softness=0.02)
light.set_position(x, y)
light.set_color(r, g, b)
light.set_intensity(val)
light.set_radius(val)
light.set_falloff(mode)
light.set_spotlight(direction, angle)
light.set_direction(degrees)
light.set_flicker(speed, amount, style)
light.set_z(z)
light.set_shadow_casting(enabled, softness=0.02)
light.get_position() -> tuple
light.get_color() -> tuple
light.get_intensity() -> float
light.get_radius() -> float
light.compute_intensity(time) -> float
light.query_point(px, py, walls=None) -> float   # 0.0=buio, 1.0=piena luce
```

### FalloffMode (enum)

```python
FalloffMode.LINEAR     # 0
FalloffMode.QUADRATIC  # 1
FalloffMode.CUBIC      # 2
```

### LightingSystem

```python
LightingSystem(ctx, program, max_lights=256)
lighting.add(x, y, radius, color, intensity, ..., cast_shadows=False, shadow_softness=0.02) -> Light
lighting.remove(light)
lighting.clear()
lighting.render(time)
lighting.set_renderer(renderer)
lighting.get_light_count() -> int
lighting.is_full() -> bool
lighting.query_point(px, py, walls=None) -> float     # max exposure from all lights
lighting.get_lights_affecting(px, py, walls=None) -> list[tuple[Light, float]]
lighting.release()
```

### FogLayer

```python
FogLayer(ctx)
fog.set_color(r, g, b)
fog.set_density(val)
fog.set_wind_speed(vx, vy)
fog.set_scale(val)
fog.set_height_falloff(val)
fog.render(time, color, density, scale, height_falloff, wind_speed, design_size)
fog.release()
```

### Shape Constants

```python
SHAPE_CIRCLE=0  SHAPE_SQUARE=1  SHAPE_SPARK=2  SHAPE_RING=3
SHAPE_STAR=4    SHAPE_DIAMOND=5 SHAPE_TRIANGLE=6 SHAPE_SOFT_DOT=7
```

### ParticlePreset (frozen dataclass)

```python
ParticlePreset(
    # Emission
    count=10, continuous=False,
    # Motion
    speed_min=50, speed_max=150, angle=0, spread=360,
    gravity=0, drag=0,
    # Lifetime
    life_min=0.3, life_max=1.0,
    # Size
    size_start=6, size_end=1,
    size_pulse_freq=0.0, size_pulse_amount=0.0,
    # Colour
    color_start=(1,1,1,1), color_end=(1,1,1,0),
    color_mid=None, color_mid_point=0.5,
    intensity=1.0, fade_in=0.0,
    # Shape
    shape=0, spark_stretch=3.0,
    ring_thickness=0.3, star_points=5, star_inner_ratio=0.4,
    vel_stretch=0.0,
    # Spin
    spin_min=0.0, spin_max=0.0,
    # Blending
    additive=True,
    # Emission shape
    emit_shape="point", emit_radius=0, emit_width=0, emit_height=0, emit_angle=0,
    # Light
    emit_light=False, light_radius=60, light_intensity=0.5, light_color=None,
    # Sub-emitter
    on_death=None, on_death_count=3,
)
```

### Built-in Presets

```python
FIRE  SMOKE  EXPLOSION  SPARK_SHOWER  RAIN  SNOW  MAGIC  BLOOD  DUST  STEAM
```

### ParticleSystem

```python
ParticleSystem(ctx, max_particles=4096)
particles.emit(x, y, preset, angle_override=None)
particles.emit_continuous(emitter_id, x, y, preset)
particles.stop_emitter(emitter_id)
particles.update(dt)
particles.render(projection_bytes, cam_x=0, cam_y=0)
particles.get_pending_lights() -> list[tuple]
particles.get_particle_count() -> int
particles.is_full() -> bool
particles.clear_all_particles()
particles.clear_emitters()
particles.is_emitter_active(emitter_id) -> bool
particles.release()
```

### Transition

```python
Transition(ctx)
transition.start(mode, duration, color=(0,0,0), reverse=False, on_complete=None)
transition.update(dt)
transition.render(screen_texture, screen_width, screen_height)
transition.stop()
transition.pause() / transition.resume()
transition.active -> bool
transition.done -> bool
transition.progress -> float
transition.get_mode() -> int
transition.get_duration() -> float
transition.get_elapsed() -> float
transition.is_reverse() -> bool
```

### TransitionMode

```python
TransitionMode.FADE
TransitionMode.DISSOLVE
TransitionMode.WIPE_LEFT
TransitionMode.WIPE_DOWN
TransitionMode.DIAMOND
```

---

## Text

### FontManager (singleton)

```python
FontManager.init(fonts_dir, font_files={"body": "...", "title": "..."})
fm = FontManager()
fm.get(name, size) -> pygame.font.Font
fm.register(name, filename)
fm.clear_cache()
fm.list_registered_fonts() -> list[str]
fm.is_font_registered(name) -> bool

FontManager.BODY        # "body"
FontManager.BODY_BOLD   # "body_bold"
FontManager.TITLE       # "title"
```

### SDFFont

```python
SDFFont(ctx, sdf_prog, font_name, cache_dir="sdf_cache")
font.draw(text, x, y, size, r=1, g=1, b=1, a=1, align_x="left", align_y="top")
# Supports multiline: "Line 1\nLine 2" renders on separate lines
# align_x is applied per line; align_y="center" uses cap-height for visual centering
font.flush()
font.measure(text, size) -> tuple[float, float]   # multiline: widest line, total height
font.get_glyph_width(char, size) -> float
font.get_line_height(size) -> float
font.has_char(char) -> bool
font.release()
```

### SDFFontCache (singleton)

```python
SDFFontCache(ctx, sdf_prog, cache_dir="assets/cache/sdf")
cache.get(font_name) -> SDFFont
cache.list_cached_fonts() -> list[str]
cache.clear()
cache.release()
SDFFontCache.instance() -> SDFFontCache
```

### BitmapFont

```python
BitmapFont(ctx, sprite_prog, pg_font, requested_size)
font.draw(batch, text, x, y, r=1, g=1, b=1, a=1, align_x="left", align_y="top")
font.measure(text) -> tuple[float, float]
font.get_glyph_width(char) -> float
font.get_line_height() -> float
font.has_char(char) -> bool
font.release()
font.atlas -> moderngl.Texture
```

### FontCache

```python
FontCache(ctx, sprite_prog)
cache.get(font_name, size) -> BitmapFont
cache.list_cached_fonts() -> list[tuple[str, int]]
cache.clear()
```

---

## Tilemap

### Tileset

```python
Tileset(texture, tile_width, tile_height, first_gid=1)
tileset.contains_gid(gid) -> bool
tileset.get_uvs(gid) -> tuple[float, float, float, float]
tileset.columns -> int
tileset.rows -> int
tileset.tile_count -> int
tileset.texture -> moderngl.Texture
```

### TileLayer

```python
TileLayer(name, width, height, tile_width, tile_height, data=None)
layer.get(tx, ty) -> int
layer.set(tx, ty, tile_id)
layer.clear()
layer.fill(tile_id)
layer.fill_rect(x, y, w, h, tile_id)
layer.is_solid(tx, ty) -> bool
layer.world_to_tile(wx, wy) -> tuple[int, int]
layer.tile_to_world(tx, ty) -> tuple[float, float]
layer.render(batch, tileset, camera, screen_w, screen_h)
layer.visible -> bool
layer.opacity -> float
layer.name -> str
layer.width -> int
layer.height -> int
```

### TileMap

```python
TileMap(width, height, tile_width, tile_height)
tilemap.add_layer(layer)
tilemap.get_layer(name) -> TileLayer | None
tilemap.remove_layer(name) -> bool
tilemap.layers -> list[TileLayer]
tilemap.tilesets -> list[Tileset]
tilemap.get_tileset_for_gid(gid) -> Tileset | None
tilemap.add_object(obj)
tilemap.get_objects(type=None) -> list[MapObject]
tilemap.remove_object(obj)
tilemap.clear_objects()
tilemap.pixel_width -> int
tilemap.pixel_height -> int
```

### MapObject (dataclass)

```python
MapObject(name, type, x, y, width=0, height=0, properties=None, polygon=None)
```

### load_map()

```python
load_map(path, texture_manager) -> TileMap
```

### ParallaxBackground

```python
ParallaxBackground()
bg.add(texture, scroll_speed, repeat_x=True, repeat_y=False, offset_y=0) -> ParallaxLayer
bg.render(batch, camera_x, camera_y, screen_w, screen_h)
bg.remove(layer)
bg.clear()
bg.layer_count -> int
```

### ParallaxLayer

```python
layer.texture -> moderngl.Texture
layer.scroll_speed -> float
layer.repeat_x -> bool
layer.repeat_y -> bool
layer.offset_y -> float
layer.tex_width -> int
layer.tex_height -> int
```

---

## UI

### Theme (dataclass)

```python
Theme(
    bg, bg_hover, bg_disabled,
    accent, accent_width, accent_width_hover,
    text, text_hover, text_disabled,
    font_size, font_ref_height, padding, border_radius, anim_speed,
    track_color, track_height, handle_color, handle_size,
    toggle_off, toggle_on,
    cursor_color, selection_color, placeholder_color,
)
```

### Widget (base class)

```python
widget.x, widget.y, widget.w, widget.h -> float
widget.theme -> Theme
widget.visible -> bool
widget.enabled -> bool
widget.selected -> bool
widget.alpha -> float                    # 0.0-1.0, global opacity (default 1.0)
widget.set_position(x, y)
widget.set_size(w, h)
widget.set_bg_color(bg, bg_hover=None, bg_disabled=None)
widget.set_text_color(text, text_hover=None, text_disabled=None)
widget.set_accent_color(accent)
widget.set_font_size(size)               # fixed font size (overrides auto-scaling)
widget.show() / widget.hide()
widget.enable() / widget.disable()
widget.is_hovered() -> bool
widget.is_pressed() -> bool
widget.hit_test(mx, my) -> bool
widget.handle_event(event) -> bool
widget.update(dt)
widget.draw_bg(batch)
widget.draw_text(font)
widget.scaled_font_size -> float   # effective font size (override or auto-scaled)

# Per-widget overrides (optional, default None = use theme)
Widget(..., bg=None, bg_hover=None, bg_disabled=None,
       accent=None, text_color=None, text_hover=None, text_disabled=None,
       font_size=None)             # fixed font size (overrides auto-scaling)
```

### Button

```python
Button(x, y, w, h, label, theme=None, on_click=None, click_sound=None, hover_sound=None, font_size=None)
```

### Toggle

```python
Toggle(x, y, w, h, label, value=False, theme=None, on_change=None, font_size=None)
toggle.value -> bool
toggle.toggle()
toggle.on_adjust(direction)        # called by FocusManager on cross-axis nav
```

### Slider

```python
Slider(x, y, w, h, label, value=0.5, min_val=0, max_val=1, step=0, theme=None, on_change=None, font_size=None)
slider.value -> float
slider.set_range(min_val, max_val)
slider.get_normalized_value() -> float
slider.set_normalized_value(val)
slider.reset()
slider.is_dragging() -> bool
slider.on_adjust(direction)        # called by FocusManager on cross-axis nav
```

### LineEdit

```python
LineEdit(x, y, w, h, placeholder="", text="", max_length=0, font=None, theme=None, on_change=None, on_submit=None, font_size=None)
edit.text -> str
edit.clear()
edit.select_all()
edit.focused -> bool
```

### Dropdown

```python
Dropdown(x, y, w, h, label, options, selected=0, theme=None, on_change=None, font_size=None)
dropdown.get_selected_index() -> int
dropdown.set_selected_index(idx)
dropdown.selected_text() -> str
dropdown.get_options() -> list[str]
dropdown.expanded -> bool
```

### FocusManager

Auto-binds `nav_up/down/left/right`, `confirm`, `back` on first use (if not already bound).

```python
FocusManager()
focus.register(widget)
focus.handle_event(event)
focus.focus_next()
focus.focus_prev()
focus.get_focused() -> Widget | None
focus.clear()
```

### VBox / HBox

Supports nesting — boxes can contain other boxes.

```python
VBox(x, y, w, h=None, spacing=10, padding=12, navigable=False)
# h given: children get equal height (distribute). h omitted: auto-calc (pack).
HBox(x, y, h, w=None, spacing=10, padding=12, navigable=False)
# w given: children get equal width (distribute). w omitted: auto-calc (pack).
layout.set_distribute(enabled)  # True = equal distribution, False = pack
layout.set_anchor(anchor_x, anchor_y, margin=0)  # position relative to screen edges
layout.add(widget)              # add widget or nested box
layout.insert(widget, idx)
layout.remove(widget)
layout.clear()
layout.contains(widget) -> bool
layout.layout()                 # recursive — lays out nested boxes too, applies anchor
layout.get_children() -> list
layout.flat_widgets() -> list[Widget]  # all leaf widgets (recursive)
layout.handle_events(events)           # recursive
layout.update(dt)                      # recursive
```

### RoundedRectRenderer

```python
RoundedRectRenderer(ctx)
rounded.draw(x, y, w, h, radius, r, g, b, a)
```

### render_widgets()

```python
render_widgets(widgets, batch, white_tex, font, rounded=None)
```

### GlyphText

```python
GlyphText(batch, font, textures, glyph_gap=2)
GlyphText.ps(batch, font, textures, style="basic", glyph_gap=2)  # PS controller glyphs
gt.draw(text, x, y, size, r=1.0, g=1.0, b=1.0, a=1.0, align_x="left", align_y="center")
gt.measure(text, size) -> (float, float)
load_ps_glyphs(textures, style="basic")  # load PS glyphs into TextureManager
```

---

## Animation

### Bone

```python
Bone(name, length=0, local_angle=0)
bone.add_child(child)
bone.world_x, bone.world_y -> float
bone.world_end_x, bone.world_end_y -> float
bone.world_angle_rad -> float
```

### Skeleton

```python
Skeleton(root_bone)
skeleton.get(name) -> Bone | None
skeleton.has_bone(name) -> bool
skeleton.bone_names -> list[str]
skeleton.solve(root_x, root_y, flip_x=False, scale=1.0)
skeleton.set_bone_length(name, length)
skeleton.scale_lengths(factor)
skeleton.remove_bone(name)
skeleton.clone() -> Skeleton
```

### Pose

```python
Pose(angles={}, offset_x=0, offset_y=0)
pose.set_angle(name, degrees)
pose.get_angle(name) -> float
Pose.lerp(a, b, t) -> Pose
Pose.lerp_into(a, b, t, out)
pose.clone() -> Pose
```

### Animation (frozen dataclass)

```python
Animation(name, keyframes=((0.0, pose), ...), loop_mode=LoopMode.LOOP, duration=1.0)
anim.sample(t) -> Pose
anim.sample_into(t, out)
```

### LoopMode

```python
LoopMode.ONCE
LoopMode.LOOP
LoopMode.PING_PONG
```

### Animator

```python
Animator()
animator.play(animation, speed=1.0, blend_time=0.15)
animator.queue(animation, blend_time=0.2)
animator.update(dt)
animator.apply(skeleton)
animator.stop()
animator.reset()
animator.seek(time)
animator.set_speed(speed)
animator.get_speed() -> float
animator.get_current_time() -> float
animator.is_finished() -> bool
animator.clear_queue()
animator.get_queue_size() -> int
animator.playing -> bool
animator.blending -> bool
animator.current_animation -> Animation | None
animator.root_offset -> tuple[float, float]
```

### AnimStateMachine

```python
AnimStateMachine(animator)
sm.add(name, animation, lock=False, blend_out=0.15)
sm.set(name, blend=0.15)
sm.force(name, blend=0.1)
sm.default -> str
sm.state -> str
sm.locked -> bool
sm.has_state(name) -> bool
sm.get_states() -> list[str]
sm.reset_to_default()
```

### Stickman

```python
Stickman(skeleton, config)
stickman.play(animation, speed=1, on_complete=None, blend_time=0.15)
stickman.queue(animation, blend_time=0.2)
stickman.stop()
stickman.update(dt)
stickman.draw(app, x, y)
stickman.flip_x -> bool
stickman.scale -> float
stickman.set_head_radius(r)
stickman.set_head_color(r, g, b, a)
stickman.set_eye_radius(r)
stickman.set_eye_color(r, g, b, a)
```

### Preset Animations

```python
IDLE, WALK, RUN, JUMP, FALL, LANDING, ATTACK
```

### Preset Builders

```python
create_default_skeleton() -> Skeleton
create_default_config() -> StickmanConfig
create_default_stickman() -> Stickman
```

### Model I/O

```python
ModelData(name, skeleton_data, config_data, animations)
save_model(model, path)
load_model(path) -> ModelData
export_animation(model, anim_name, path)
build_animation(keyframes, duration, loop_mode) -> Animation
create_empty_model(name) -> ModelData
model_from_defaults() -> ModelData
```

---

## Audio

### SoundManager

```python
SoundManager()
sound.init(sfx_path="assets/sfx", music_path="assets/music")
sound.load(name, filename) -> pygame.mixer.Sound
sound.play(name, volume=1.0, pitch_var=0.0, volume_var=0.0) -> Channel | None
sound.play_at(name, x, y, listener_x, listener_y, max_distance=500, volume=1.0, pitch_var=0.0, volume_var=0.0) -> Channel | None
sound.stop_all_sfx()
sound.play_music(name, loop=True, fade_in=0.0)
sound.stop_music(fade_out=0.0)
sound.pause_music()
sound.resume_music()
sound.set_master_volume(vol)
sound.set_sfx_volume(vol)
sound.set_music_volume(vol)
sound.mute() / sound.unmute()
sound.is_muted() -> bool
sound.get_master_volume() -> float
sound.get_sfx_volume() -> float
sound.get_music_volume() -> float
sound.is_music_playing() -> bool
sound.get_current_music() -> str | None
sound.is_sound_loaded(name) -> bool
sound.get_loaded_sounds() -> list[str]
sound.release(name)
sound.release_all()
```

---

## Input

### InputManager

```python
InputManager()
input.bind(action, *triggers)
input.bind_axis(action, negative=[], positive=[], stick=None)
input.unbind(action)
input.is_bound(action) -> bool
input.get_bindings(action) -> list
input.get_all_actions() -> list[str]
input.update(events)
input.pressed(action) -> bool
input.held(action) -> bool
input.released(action) -> bool
input.axis(action) -> float
input.has_controller() -> bool
input.get_controller_name() -> str | None
```

### Mouse

```python
Mouse.LEFT, Mouse.MIDDLE, Mouse.RIGHT
```

### Pad

```python
Pad.A, Pad.B, Pad.X, Pad.Y
Pad.LB, Pad.RB, Pad.LT, Pad.RT
Pad.LSTICK, Pad.RSTICK
Pad.DPAD_UP, Pad.DPAD_DOWN, Pad.DPAD_LEFT, Pad.DPAD_RIGHT
Pad.START, Pad.BACK
```

### Stick

```python
Stick.LEFT_X, Stick.LEFT_Y, Stick.RIGHT_X, Stick.RIGHT_Y
```

---

## Networking

### NetworkManager (singleton `Net`)

```python
Net = NetworkManager()

# Lifecycle
Net.init(transport="steam", app_id=480)          # init transport without connecting
Net.host(port=7777, transport="steam", app_id=480)
Net.join(address="127.0.0.1", port=7777, transport="steam", app_id=480)
Net.disconnect()
Net.poll(dt=0.0)

# Callbacks
Net.on_connect(fn)           # fn(peer_id: int)
Net.on_disconnect(fn)        # fn(peer_id: int)

# Network events
@Net.on_event("name")        # decorator: fn(peer_id, *args)
Net.emit("name", *args, reliable=True)           # broadcast to all
Net.emit_to(pid, "name", *args, reliable=True)   # to specific peer
Net.emit_to_host("name", *args, reliable=True)   # to host only
Net.emit_to_client(pid, "name", *args, reliable=True)  # to client (rejects pid=0)

# Node factory
Net.register_node_type(name, factory, auto_spawn=False)
Net.spawn(type_name, **kwargs) -> node
Net.despawn(node)
Net.get_node(peer_id, type_name=None) -> node | None
Net.nodes -> dict[int, node]                     # live dict, auto-maintained
Net.on_node_created(fn)      # fn(peer_id, node)
Net.on_node_removed(fn)      # fn(peer_id, node)

# State
Net.is_host -> bool
Net.is_connected -> bool
Net.local_id -> int
Net.local_name -> str                            # Steam player name
Net.peer_count -> int
Net.peers -> list[int]
Net.get_peer(peer_id) -> Peer | None
Net.get_player_name(peer_id) -> str
Net.sync_tick_rate -> float   # get/set Hz (default 20)
Net.obj_per_owner -> int      # get/set max objects per owner (default 1000)
Net.rpc_rate_limit -> int     # get/set max RPC relay/peer/sec (default 300, 0=off)
Net.stats -> dict             # {"sent_bps", "recv_bps", "sent_pps", "recv_pps", "peers"}
Net.context                   # get/set application context (accessible from RPCs)

# Network clock
Net.net_time -> float         # synchronized time (host = perf_counter, clients aligned)
Net.clock_offset -> float     # offset from host clock (seconds)
Net.clock_synced -> bool      # True after first sync

# Lobby
Net.lobby -> LobbyManager
Net.check_launch_invite() -> bool  # check Steam launch args for invite
```

### Peer (dataclass)

```python
Peer(id, address="", port=0, steam_id=0, name="", rtt=0.0, state="connecting")
peer.is_connected -> bool
peer.uptime -> float
```

### synced() descriptor

```python
synced(default=None, reliable=False, interpolate=False, lerp_speed=10.0)

class Player:
    x = synced(0.0, interpolate=True, lerp_speed=15.0)   # unreliable, interpolated
    y = synced(0.0, interpolate=True, lerp_speed=15.0)
    health = synced(100, reliable=True)                   # reliable channel
```

### @rpc decorator

```python
rpc(target="all", reliable=True)
host_only                    # decorator: method runs only if Net.is_host

# Targets
RPCTarget.ALL       # "all"
RPCTarget.HOST      # "host"
RPCTarget.OTHERS    # "others"
RPCTarget.PEER      # "peer" (via _rpc_peer_id=N, routed through host)
```

### NetNode (base class)

```python
class NetNode:
    def __init__(self, owner: int):
        self._net_owner = owner
        self._net_dirty: set[str] = set()
        self._net_type_name: str = ""
```

### LobbyManager

```python
Net.lobby.create(name="", max_players=4, public=False, on_created=None)
Net.lobby.join_code(code, on_joined=None)
Net.lobby.invite(steam_id) -> bool           # Steam: send friend invite
Net.lobby.leave()
Net.lobby.get_friends() -> list[dict]        # Steam: online friends list
Net.lobby.get_members() -> list[dict]        # Steam: lobby members
Net.lobby.set_data(key, value) -> bool       # Steam: lobby metadata
Net.lobby.get_data(key) -> str               # Steam: read metadata
Net.lobby.code -> str | None
Net.lobby.name -> str
Net.lobby.max_players -> int
Net.lobby.player_count -> int
Net.lobby.is_in_lobby -> bool
Net.lobby.is_full -> bool
Net.lobby.is_steam -> bool
```

---

## App

```python
App(width=1280, height=720, title="PyLuxel",
    design_width=None, design_height=None,
    fps=60, vsync=False, resizable=False, centered=False,
    clear_color=(0.05, 0.04, 0.07))

# Hooks (subclass or decorator)
app.setup()
app.update(dt) / @app.on_update
app.draw() / @app.on_draw
app.draw_lights() / @app.on_draw_lights
app.shadow_casters() / @app.on_shadow_casters
app.draw_overlay() / @app.on_draw_overlay
app.handle_event(event) / @app.on_event
app.handle_resize(w, h) / @app.on_resize

# Drawing
app.draw_sprite(x, y, w, h, texture, u0, v0, u1, v1, r, g, b, a, angle)
app.draw_rect(x, y, w, h, r, g, b, a, angle)
app.draw_circle(x, y, radius, r, g, b, a)
app.draw_triangle(x, y, w, h, r, g, b, a, angle)
app.draw_polygon(x, y, radius, sides, r, g, b, a, angle)
app.draw_star(x, y, radius, points, inner_ratio, r, g, b, a, angle)
app.draw_capsule(x, y, w, h, r, g, b, a, angle)
app.draw_line(x1, y1, x2, y2, r, g, b, a, width)
app.draw_text(text, x, y, size, font, r, g, b, a, align_x, align_y)
app.measure_text(text, size, font) -> tuple[float, float]

# Lights & effects
app.add_light(...) -> Light
app.remove_light(light)
app.clear_lights()
app.add_shockwave(x, y, max_radius, thickness, strength)
app.add_heat_haze(x, y, w, h, strength, speed, scale) -> HeatHaze
app.remove_heat_haze(haze)
app.start_transition(mode, duration, color, reverse, on_complete)
app.stop_transition()

# Window
app.run()
app.quit()
app.toggle_fullscreen()
app.set_fullscreen(bool)
app.set_resolution(w, h)
app.set_vsync(bool)
app.set_window_title(str)
app.screenshot(path)
app.ShowFPS(val=True) / app.ShowStats(val=True)
app.scenes -> SceneManager             # scene manager integrato
```

---

## Scene Manager

### Scene (base class)

```python
from pyluxel import Scene, SceneManager

class MenuScene(Scene):
    def setup(self):      ...   # una volta, al primo switch
    def enter(self):      ...   # ogni volta che diventa attiva
    def exit(self):       ...   # quando viene disattivata
    def update(self, dt): ...
    def draw(self):       ...
    def draw_lights(self):     ...
    def shadow_casters(self):  ...
    def draw_overlay(self):    ...
    def handle_event(self, event): ...

# Attributi disponibili dopo attach:
scene.app -> App
scene.manager -> SceneManager
```

### SceneManager

```python
# Integrato in App come app.scenes
app.scenes.register(name, SceneClass)
app.scenes.switch(name)                # cambia scena (svuota stack)
app.scenes.push(name)                  # sovrappone scena
app.scenes.pop()                       # torna alla precedente
app.scenes.reset(name)                 # forza re-setup
app.scenes.current -> Scene | None
app.scenes.stack_depth -> int
```

---

## Physics

### Collision

```python
from pyluxel import (aabb_vs_aabb, aabb_vs_point, aabb_vs_circle,
                      aabb_overlap, circle_vs_circle, circle_vs_point,
                      ray_vs_aabb, collides_aabb_list)

# AABB (x, y = top-left, w, h = dimensioni)
aabb_vs_aabb(x1, y1, w1, h1, x2, y2, w2, h2) -> bool
aabb_vs_point(rx, ry, rw, rh, px, py) -> bool
aabb_vs_circle(rx, ry, rw, rh, cx, cy, radius) -> bool
aabb_overlap(x1, y1, w1, h1, x2, y2, w2, h2) -> tuple[float, float] | None

# Cerchi
circle_vs_circle(x1, y1, r1, x2, y2, r2) -> bool
circle_vs_point(cx, cy, radius, px, py) -> bool

# Ray (da origine a origine+dir, t in [0,1])
ray_vs_aabb(ox, oy, dx, dy, rx, ry, rw, rh) -> float | None

# Utility: test quadrato centrato vs lista di muri AABB
collides_aabb_list(x, y, half, walls) -> bool
```

---

## Timer

```python
from pyluxel import Timer

timer = Timer(duration=90.0, on_complete=callback, auto_start=True)
timer.update(dt)
timer.start()
timer.pause()
timer.reset(duration=None)

timer.remaining -> float       # secondi rimanenti
timer.elapsed -> float         # secondi trascorsi
timer.duration -> float        # durata totale
timer.progress -> float        # 0.0 -> 1.0
timer.running -> bool
timer.finished -> bool
timer.formatted(show_ms=False) -> str   # "01:30" o "01:30.45"
```

---

## Utilities

### Paths

```python
from pyluxel import base_path, user_data_dir

base_path() -> Path                              # project root (dev) o extraction dir (frozen)
user_data_dir("my_game") -> Path                 # OS-specific user data directory
```

Internal path utilities (usate dai loader dell'engine):

```python
from pyluxel.core import paths

paths.exe_dir() -> str                                         # directory dell'eseguibile
paths.join("assets", "maps", "test.tmx") -> str                # os.path.join
paths.resolve_relative("assets/maps/test.tmx", "../t/C.tsx")   # -> "assets/t/C.tsx"
paths.filename("assets/sprites/player.png") -> str              # -> "player.png"
paths.extension("test.tmx") -> str                              # -> ".tmx"
paths.exists("assets/maps/test.tmx") -> bool                   # os.path.exists
```

### Asset PAK

```python
from pyluxel import asset_open, asset_exists, init_pak, has_pak

init_pak("data.pak")                             # carica pak (auto da App se data.pak esiste)
init_pak("data.pak", key=b"custom_key")          # con chiave XOR personalizzata
has_pak() -> bool                                # True se pak attivo
asset_open("assets/data/enemies.json") -> BinaryIO  # legge da pak o da disco
asset_exists("assets/data/config.json") -> bool     # esiste nel pak o su disco
```

CLI: `pyluxel pak assets/ -o data.pak --exclude cache`

Vedi [pak.md](pak.md) per la documentazione completa.

### Debug

```python
from pyluxel import cprint

cprint.ok("message")        # green
cprint.info("message")      # blue
cprint.warning("message")   # yellow
cprint.error("message")     # red
```

### GPUStats

```python
from pyluxel import GPUStats

GPUStats.draw_calls -> int
GPUStats.sprites -> int
GPUStats.reset_frame()
GPUStats.calc_engine_vram(renderer, batch, textures, lighting, sdf_cache, white_tex) -> float
GPUStats.query_gpu_vram(ctx) -> tuple[float, float]   # (total_mb, available_mb)
```
