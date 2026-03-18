# Animation

Skeletal animation system with forward kinematics, keyframe interpolation, crossfade blending, state machine, and procedural stickman rendering.

---

## Bone & Skeleton

### Bone

A single bone with a local angle relative to its parent. Angles are in **degrees**.

```python
from pyluxel import Bone, Skeleton

# Create bone hierarchy
hip = Bone("hip", length=0)          # root (no length)
spine = Bone("spine", length=30, local_angle=0)
head = Bone("head", length=15, local_angle=0)

hip.add_child(spine)
spine.add_child(head)

# Properties (after solve)
bone.world_x, bone.world_y          # start position
bone.world_end_x, bone.world_end_y  # end position
bone.world_angle_rad                # world angle in radians
```

### Skeleton

Tree of bones with forward kinematics solver.

```python
skeleton = Skeleton(hip)

# Look up bones by name
bone = skeleton.get("spine")     # Bone or None
skeleton.has_bone("spine")       # True
skeleton.bone_names              # ["hip", "spine", "head", ...]

# Forward kinematics: compute world positions
skeleton.solve(
    root_x=400, root_y=300,    # root position (design space)
    flip_x=False,               # mirror horizontally
    scale=1.0,                  # scale bone lengths
)

# Modify skeleton
skeleton.set_bone_length("spine", 40)
skeleton.scale_lengths(1.5)      # scale all bones
skeleton.remove_bone("head")

# Deep copy
copy = skeleton.clone()
```

---

## Pose

A snapshot of bone angles used as a keyframe. Only bones present in the `angles` dict are animated.

```python
from pyluxel import Pose

pose = Pose(
    angles={
        "spine": 10.0,
        "l_upper_arm": -30.0,
        "r_upper_arm": 30.0,
    },
    offset_x=0.0,   # visual root offset
    offset_y=-5.0,   # visual root offset (e.g., for jump arc)
)

# Modify
pose.set_angle("spine", 15.0)
pose.get_angle("spine")   # 15.0

# Interpolate (shortest-path for angles)
blended = Pose.lerp(pose_a, pose_b, t=0.5)

# Zero-allocation interpolation
Pose.lerp_into(pose_a, pose_b, t=0.5, out=result_pose)

# Clone
copy = pose.clone()
```

---

## Animation

Immutable sequence of keyframes with a loop mode and duration.

```python
from pyluxel import Animation, LoopMode, Pose

walk = Animation(
    name="walk",
    keyframes=(
        (0.0, Pose({"l_upper_leg": 30, "r_upper_leg": -30})),
        (0.5, Pose({"l_upper_leg": -30, "r_upper_leg": 30})),
        (1.0, Pose({"l_upper_leg": 30, "r_upper_leg": -30})),
    ),
    loop_mode=LoopMode.LOOP,      # ONCE, LOOP, or PING_PONG
    duration=0.8,                   # total duration in seconds
)

# Sample a pose at a given time
pose = walk.sample(t=0.4)         # returns Pose

# Zero-allocation sample
walk.sample_into(t=0.4, out=my_pose)
```

### Loop Modes

| Mode | Description |
|------|-------------|
| `LoopMode.ONCE` | Play once, then stop |
| `LoopMode.LOOP` | Repeat from the beginning |
| `LoopMode.PING_PONG` | Play forward, then backward, repeat |

---

## Animator

Plays animations with crossfade blending, speed control, and queueing.

```python
from pyluxel import Animator

animator = Animator()

# Play an animation
animator.play(walk, speed=1.0, blend_time=0.15)

# Queue next animation (plays after current finishes)
animator.queue(idle, blend_time=0.2)

# Each frame
animator.update(dt)
animator.apply(skeleton)   # write pose angles to skeleton bones
skeleton.solve(x, y)       # compute world positions

# Properties
animator.playing             # True while playing
animator.blending            # True during crossfade
animator.current_animation   # Animation or None
animator.root_offset         # (offset_x, offset_y) from current pose
animator.is_finished()       # True if ONCE animation completed
animator.get_current_time()  # playback time in seconds
animator.get_speed()         # playback speed

# Control
animator.set_speed(2.0)     # double speed
animator.seek(0.5)          # jump to time
animator.stop()
animator.reset()            # rewind to 0
animator.clear_queue()
animator.get_queue_size()
```

---

## AnimStateMachine

State-based animation controller with locked states (e.g., attack, jump) that auto-return to a default state.

```python
from pyluxel import AnimStateMachine, IDLE, WALK, RUN, JUMP, ATTACK

sm = AnimStateMachine(animator)

# Register states
sm.add("idle", IDLE)
sm.add("walk", WALK)
sm.add("run", RUN)
sm.add("jump", JUMP, lock=True, blend_out=0.15)    # can't be interrupted
sm.add("attack", ATTACK, lock=True, blend_out=0.1)

# Set default (locked states return here)
sm.default = "idle"
sm.set("idle")

# Transition (with optional crossfade)
sm.set("walk", blend=0.15)     # smooth transition
sm.set("attack", blend=0.1)   # locks until complete, then returns to idle

# Force transition (ignores lock, e.g., for death)
sm.force("die", blend=0.1)

# Properties
sm.state      # current state name
sm.locked     # True if in a locked state

# Utilities
sm.has_state("walk")
sm.get_states()          # ["idle", "walk", "run", ...]
sm.reset_to_default()    # force back to default
```

---

## Stickman

Combines a Skeleton, Animator, and visual config for procedural stickman rendering.

```python
from pyluxel import (
    Stickman, StickmanConfig, BoneVisual, EyeConfig,
    create_default_skeleton, create_default_config, create_default_stickman,
    IDLE, WALK
)

# Quick setup with defaults
guy = create_default_stickman()
guy.play(IDLE)

# Each frame
guy.update(dt)
guy.draw(app, x=400, y=300)

# Direction
guy.flip_x = True   # face left
guy.scale = 1.5     # scale up
```

### Custom Configuration

```python
config = StickmanConfig(
    head_radius=12.0,
    head_color=(1.0, 0.9, 0.8, 1.0),
    head_bone="head",
    eyes=EyeConfig(
        enabled=True,
        radius=2.5,
        offset_x=3.5,
        spacing=3.5,
        offset_y=1.0,
        color=(0.1, 0.1, 0.15, 1.0),
    ),
    default_visual=BoneVisual(
        draw_bone=True,
        draw_joint=True,
        bone_thickness=6.0,
        joint_radius=4.0,
        bone_color=(1.0, 1.0, 1.0, 1.0),
        joint_color=(0.9, 0.9, 0.9, 1.0),
    ),
    bone_visuals={
        "spine": BoneVisual(bone_thickness=8.0),
    },
)

skeleton = create_default_skeleton()
guy = Stickman(skeleton, config)
```

### Stickman Methods

| Method | Description |
|--------|-------------|
| `play(animation, speed, on_complete, blend_time)` | Play animation |
| `queue(animation, blend_time)` | Queue next animation |
| `stop()` | Stop animation |
| `update(dt)` | Update animation |
| `draw(app, x, y)` | Render at position |
| `set_head_radius(r)` | Change head size |
| `set_head_color(r, g, b, a)` | Change head color |
| `set_eye_radius(r)` | Change eye size |
| `set_eye_color(r, g, b, a)` | Change eye color |

---

## Preset Animations

Built-in animations for a standard 11-bone humanoid skeleton.

```python
from pyluxel import IDLE, WALK, RUN, JUMP, FALL, LANDING, ATTACK

guy.play(IDLE)
guy.play(WALK, blend_time=0.15)
guy.play(ATTACK, on_complete=lambda: guy.play(IDLE, blend_time=0.1))
```

| Preset | Loop Mode | Description |
|--------|-----------|-------------|
| `IDLE` | LOOP | Standing idle with subtle breathing |
| `WALK` | LOOP | Walking cycle |
| `RUN` | LOOP | Running cycle |
| `JUMP` | ONCE | Jump launch |
| `FALL` | LOOP | Falling pose |
| `LANDING` | ONCE | Landing recovery |
| `ATTACK` | ONCE | Punch/attack |

### Preset Builders

```python
from pyluxel import create_default_skeleton, create_default_config, create_default_stickman

skeleton = create_default_skeleton()   # 11-bone humanoid
config = create_default_config()       # default visual config
guy = create_default_stickman()        # skeleton + config + ready to use
```

---

## Model I/O

Save and load complete animation models (skeleton + config + animations) as JSON.

```python
from pyluxel import (
    ModelData, save_model, load_model, export_animation,
    build_animation, create_empty_model, model_from_defaults,
)

# Create from defaults
model = model_from_defaults()

# Save to disk
save_model(model, "player.model.json")

# Load from disk
model = load_model("player.model.json")

# Export a single animation
export_animation(model, "walk", "walk.anim.json")

# Build Animation from raw keyframes
anim = build_animation(
    keyframes=[(0.0, pose_a), (0.5, pose_b), (1.0, pose_a)],
    duration=0.8,
    loop_mode=LoopMode.LOOP,
)

# Create empty model
model = create_empty_model("my_character")
```
