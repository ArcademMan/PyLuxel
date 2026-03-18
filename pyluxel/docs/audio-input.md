# Audio & Input

Sound effects, music streaming, spatial audio, and action-based input abstraction for keyboard, mouse, and gamepad.

---

## SoundManager

Loads, caches, and plays sound effects and music. Follows the same load/cache/release pattern as `TextureManager`.

```python
from pyluxel import SoundManager

sound = SoundManager()
sound.init(sfx_path="assets/sfx", music_path="assets/music")
```

> When using the `App` class, a global singleton `Sound` is already available.

### Loading & Playing SFX

```python
from pyluxel import Sound

# Load a sound effect (cached by name)
Sound.load("jump", "jump.wav")
Sound.load("hit", "hit.wav")

# Play
Sound.play("jump")

# Play with variation (adds randomness to prevent repetitive sounds)
Sound.play("hit", volume=0.8, pitch_var=0.1, volume_var=0.05)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `name` | — | Key used when loading the sound |
| `volume` | `1.0` | Local volume (0.0–1.0), scaled by master and SFX volumes |
| `pitch_var` | `0.0` | Random pitch variation (0.1 = ±10%) |
| `volume_var` | `0.0` | Random volume variation (0.05 = ±5%) |

### Spatial Audio

2D positional audio with distance attenuation and stereo panning.

```python
# Play at a world position (design space)
Sound.play_at(
    "hit",
    x=500, y=300,                   # sound source position
    listener_x=player_x,            # listener position
    listener_y=player_y,
    max_distance=500.0,             # beyond this distance, sound is silent
    volume=1.0,
    pitch_var=0.1,
    volume_var=0.05,
)
```

Attenuation is linear. Stereo panning is computed from the horizontal distance to the listener.

### Music

One music track plays at a time (streamed, not cached). File extensions (`.ogg`, `.mp3`, `.wav`, `.flac`) are resolved automatically.

```python
# Play music (loops by default)
Sound.play_music("theme", loop=True, fade_in=1.0)

# Control
Sound.pause_music()
Sound.resume_music()
Sound.stop_music(fade_out=2.0)

# Query
Sound.is_music_playing()       # True/False
Sound.get_current_music()      # "theme" or None
```

### Volume Control

Three-tier volume system: master scales everything, SFX and music are independent sub-volumes.

```python
Sound.set_master_volume(0.8)   # scales all audio
Sound.set_sfx_volume(0.7)      # SFX sub-volume
Sound.set_music_volume(0.5)    # music sub-volume

# Mute / unmute (preserves previous volume)
Sound.mute()
Sound.unmute()
Sound.is_muted()               # True/False

# Query
Sound.get_master_volume()
Sound.get_sfx_volume()
Sound.get_music_volume()
```

### Cache Management

```python
Sound.is_sound_loaded("jump")      # True if cached
Sound.get_loaded_sounds()          # ["jump", "hit", ...]

Sound.release("jump")             # release one SFX
Sound.release_all()               # stop everything, clear cache
Sound.stop_all_sfx()              # stop all playing SFX channels
```

---

## InputManager

Action-based input abstraction. Bind logical action names to physical inputs (keyboard keys, mouse buttons, gamepad buttons/sticks), then query actions instead of raw device state.

```python
from pyluxel import Input, Mouse, Pad, Stick
import pygame
```

> `Input` is a global singleton instance of `InputManager`. Always use `Input`, not raw `pygame.key.get_pressed()`.

### Binding Actions

```python
# Keyboard
Input.bind("jump", pygame.K_SPACE, pygame.K_UP)
Input.bind("quit", pygame.K_ESCAPE)

# Mouse
Input.bind("shoot", Mouse.LEFT)
Input.bind("aim", Mouse.RIGHT)

# Gamepad buttons
Input.bind("jump", pygame.K_SPACE, Pad.A)
Input.bind("attack", pygame.K_z, Pad.X)

# Gamepad triggers (analog axes used as digital buttons)
Input.bind("shoot", Mouse.LEFT, Pad.RT)
```

### Binding Axes

Combine digital keys and analog sticks into a single axis value (-1.0 to 1.0).

```python
Input.bind_axis("move_x",
    negative=[pygame.K_LEFT, pygame.K_a, Pad.DPAD_LEFT],
    positive=[pygame.K_RIGHT, pygame.K_d, Pad.DPAD_RIGHT],
    stick=Stick.LEFT_X,
)

Input.bind_axis("move_y",
    negative=[pygame.K_UP, pygame.K_w, Pad.DPAD_UP],
    positive=[pygame.K_DOWN, pygame.K_s, Pad.DPAD_DOWN],
    stick=Stick.LEFT_Y,
)
```

Digital inputs produce -1.0 or 1.0. The analog stick provides -1.0 to 1.0 with a deadzone (0.15). Whichever has greater magnitude wins.

### Querying Input

```python
# Call once per frame (App does this automatically)
Input.update(events)

# Digital queries
Input.pressed("jump")     # True on the frame the action was first pressed
Input.held("jump")        # True while held down
Input.released("jump")    # True on the frame the action was released

# Analog axis
dx = Input.axis("move_x")   # -1.0 to 1.0
dy = Input.axis("move_y")
```

### Management

```python
Input.unbind("jump")                  # remove all bindings for an action
Input.is_bound("jump")               # True if action has bindings
Input.get_bindings("jump")           # list of triggers
Input.get_all_actions()              # sorted list of all action names

# Gamepad
Input.has_controller()               # True if a gamepad is connected
Input.get_controller_name()          # "Xbox Controller" or None
```

Gamepad hot-plug is handled automatically. When a controller is connected or disconnected, the system updates seamlessly.

---

## Mouse Buttons

```python
from pyluxel import Mouse

Mouse.LEFT      # left click
Mouse.MIDDLE    # middle click
Mouse.RIGHT     # right click
```

---

## Gamepad Buttons (Pad)

```python
from pyluxel import Pad

# Face buttons
Pad.A, Pad.B, Pad.X, Pad.Y

# Shoulders
Pad.LB, Pad.RB

# Triggers (analog, treated as digital with threshold)
Pad.LT, Pad.RT

# Sticks (press)
Pad.LSTICK, Pad.RSTICK

# D-pad
Pad.DPAD_UP, Pad.DPAD_DOWN, Pad.DPAD_LEFT, Pad.DPAD_RIGHT

# System
Pad.START, Pad.BACK
```

---

## Analog Sticks (Stick)

```python
from pyluxel import Stick

Stick.LEFT_X     # left stick horizontal
Stick.LEFT_Y     # left stick vertical
Stick.RIGHT_X    # right stick horizontal
Stick.RIGHT_Y    # right stick vertical
```

---

## Complete Example

```python
from pyluxel import App, Input, Sound, Mouse, Pad, Stick
import pygame

class Game(App):
    def setup(self):
        # Input bindings
        Input.bind("jump", pygame.K_SPACE, Pad.A)
        Input.bind("quit", pygame.K_ESCAPE)
        Input.bind("shoot", Mouse.LEFT, Pad.RT)
        Input.bind_axis("move_x",
            negative=[pygame.K_LEFT, Pad.DPAD_LEFT],
            positive=[pygame.K_RIGHT, Pad.DPAD_RIGHT],
            stick=Stick.LEFT_X)

        # Load sounds
        Sound.init("assets/sfx", "assets/music")
        Sound.load("jump", "jump.wav")
        Sound.load("shoot", "shoot.wav")
        Sound.play_music("theme")

        self.x = 640

    def update(self, dt):
        if Input.pressed("quit"):
            self.quit()

        self.x += Input.axis("move_x") * 200 * dt

        if Input.pressed("jump"):
            Sound.play("jump", pitch_var=0.05)

        if Input.pressed("shoot"):
            Sound.play("shoot")

    def draw(self):
        self.draw_circle(self.x, 360, 20, r=0, g=1, b=0.5)

Game(1280, 720, "Audio & Input Demo").run()
```
