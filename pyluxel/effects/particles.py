"""pyluxel.effects.particles -- GPU-batched 2D particle system with procedural shapes."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace, fields

import numpy as np
import moderngl

from pyluxel.debug import cprint

from pyluxel.shaders import load_shader

# ---------------------------------------------------------------------------
# Shape constants
# ---------------------------------------------------------------------------

SHAPE_CIRCLE = 0
SHAPE_SQUARE = 1
SHAPE_SPARK = 2
SHAPE_RING = 3
SHAPE_STAR = 4
SHAPE_DIAMOND = 5
SHAPE_TRIANGLE = 6
SHAPE_SOFT_DOT = 7

# ---------------------------------------------------------------------------
# Preset
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParticlePreset:
    """Immutable particle emission config.  Define once, reuse everywhere."""

    # Emission
    count: int = 10                     # burst: total particles | continuous: particles/sec
    continuous: bool = False

    # Motion
    speed_min: float = 50.0
    speed_max: float = 150.0
    angle: float = 0.0                  # centre direction (degrees, 0 = right)
    spread: float = 360.0              # half-cone (degrees, 360 = omni)
    gravity: float = 0.0               # px/s^2 downward (+Y in screen space)
    drag: float = 0.0                  # velocity damping (0 = none, higher = faster stop)

    # Lifetime (seconds)
    life_min: float = 0.3
    life_max: float = 1.0

    # Size (pixels)
    size_start: float = 6.0
    size_end: float = 1.0

    # Colour (RGBA, lerped over lifetime)
    color_start: tuple = (1.0, 1.0, 1.0, 1.0)
    color_end: tuple = (1.0, 1.0, 1.0, 0.0)

    # Shape:  0-7 (see SHAPE_* constants)
    shape: int = 0
    spark_stretch: float = 3.0         # spark-only: length / width ratio

    # Blending:  True = additive (ONE, ONE),  False = alpha (SRC_ALPHA, 1-SRC_ALPHA)
    additive: bool = True

    # Optional aggregate light per emit() call
    emit_light: bool = False
    light_radius: float = 60.0
    light_intensity: float = 0.5
    light_color: tuple | None = None   # None -> uses color_start[:3]

    # --- Shape params ---
    ring_thickness: float = 0.3        # shape=RING: inner radius ratio (0-1)
    star_points: int = 5               # shape=STAR: number of points (3-8)
    star_inner_ratio: float = 0.4      # shape=STAR: inner/outer radius

    # --- HDR intensity ---
    intensity: float = 1.0             # colour multiplier (>1.0 for bloom glow)

    # --- Velocity stretching (any shape) ---
    vel_stretch: float = 0.0           # 0 = no stretch, >0 = elongate along velocity

    # --- Fade-in ---
    fade_in: float = 0.0              # fraction of lifetime spent fading in (0-1)

    # --- 3-stop colour ---
    color_mid: tuple | None = None     # None = 2-stop. Tuple(RGBA) = 3-stop
    color_mid_point: float = 0.5       # normalised time where mid-colour peaks

    # --- Spin / rotation ---
    spin_min: float = 0.0              # angular velocity (degrees/sec)
    spin_max: float = 0.0

    # --- Size oscillation ---
    size_pulse_freq: float = 0.0       # Hz (0 = disabled)
    size_pulse_amount: float = 0.0     # amplitude in pixels

    # --- Emission shape ---
    emit_shape: str = "point"          # "point" | "ring" | "line" | "rect"
    emit_radius: float = 0.0          # ring emitter radius
    emit_width: float = 0.0           # line/rect width
    emit_height: float = 0.0          # rect height
    emit_angle: float = 0.0           # line rotation (degrees)

    # --- Sub-emitter ---
    on_death: 'ParticlePreset | None' = None
    on_death_count: int = 3


# ---------------------------------------------------------------------------
# Built-in presets
# ---------------------------------------------------------------------------

FIRE = ParticlePreset(
    count=20, speed_min=30, speed_max=80,
    angle=270, spread=25,
    gravity=-20, drag=1.5,
    life_min=0.3, life_max=0.8,
    size_start=10, size_end=2,
    color_start=(1.0, 0.9, 0.3, 1.0),
    color_mid=(1.0, 0.3, 0.0, 0.8),
    color_mid_point=0.4,
    color_end=(0.3, 0.05, 0.0, 0.0),
    shape=SHAPE_SOFT_DOT,
    additive=True,
    intensity=1.5,
    fade_in=0.1,
)

SMOKE = ParticlePreset(
    count=8, speed_min=10, speed_max=40,
    angle=270, spread=30,
    gravity=-15, drag=2.0,
    life_min=0.8, life_max=2.0,
    size_start=8, size_end=30,
    color_start=(0.5, 0.5, 0.5, 0.4),
    color_end=(0.3, 0.3, 0.3, 0.0),
    shape=SHAPE_SOFT_DOT,
    additive=False,
    fade_in=0.2,
)

EXPLOSION = ParticlePreset(
    count=40, speed_min=100, speed_max=300,
    angle=0, spread=360,
    gravity=50, drag=3.0,
    life_min=0.2, life_max=0.6,
    size_start=8, size_end=2,
    color_start=(1.0, 0.9, 0.5, 1.0),
    color_mid=(1.0, 0.4, 0.0, 0.9),
    color_mid_point=0.3,
    color_end=(0.4, 0.1, 0.0, 0.0),
    shape=SHAPE_CIRCLE,
    additive=True,
    intensity=2.0,
    vel_stretch=2.0,
    emit_shape="ring", emit_radius=5,
)

SPARK_SHOWER = ParticlePreset(
    count=15, speed_min=60, speed_max=200,
    angle=300, spread=40,
    gravity=120, drag=0.5,
    life_min=0.3, life_max=0.7,
    size_start=4, size_end=1,
    color_start=(1.0, 0.9, 0.5, 1.0),
    color_end=(1.0, 0.5, 0.0, 0.0),
    shape=SHAPE_SPARK, spark_stretch=4.0,
    additive=True,
    intensity=1.8,
)

RAIN = ParticlePreset(
    count=80, continuous=True,
    speed_min=400, speed_max=500,
    angle=95, spread=5,
    gravity=0, drag=0,
    life_min=0.3, life_max=0.5,
    size_start=3, size_end=3,
    color_start=(0.6, 0.7, 0.9, 0.6),
    color_end=(0.6, 0.7, 0.9, 0.0),
    shape=SHAPE_SPARK, spark_stretch=6.0,
    additive=False,
    emit_shape="line", emit_width=1400,
)

SNOW = ParticlePreset(
    count=30, continuous=True,
    speed_min=20, speed_max=50,
    angle=90, spread=30,
    gravity=10, drag=0.5,
    life_min=3.0, life_max=6.0,
    size_start=4, size_end=3,
    color_start=(1.0, 1.0, 1.0, 0.8),
    color_end=(1.0, 1.0, 1.0, 0.0),
    shape=SHAPE_SOFT_DOT,
    additive=False,
    spin_min=-90, spin_max=90,
    size_pulse_freq=0.5, size_pulse_amount=1.0,
    emit_shape="line", emit_width=1400,
)

MAGIC = ParticlePreset(
    count=12, speed_min=20, speed_max=60,
    angle=0, spread=360,
    gravity=-10, drag=2.0,
    life_min=0.5, life_max=1.2,
    size_start=5, size_end=1,
    color_start=(0.5, 0.3, 1.0, 1.0),
    color_mid=(0.2, 0.8, 1.0, 0.8),
    color_mid_point=0.5,
    color_end=(0.1, 0.4, 1.0, 0.0),
    shape=SHAPE_STAR, star_points=4, star_inner_ratio=0.3,
    additive=True,
    intensity=1.5,
    spin_min=-180, spin_max=180,
    fade_in=0.15,
)

BLOOD = ParticlePreset(
    count=15, speed_min=60, speed_max=180,
    angle=0, spread=360,
    gravity=200, drag=1.0,
    life_min=0.2, life_max=0.5,
    size_start=4, size_end=2,
    color_start=(0.8, 0.0, 0.0, 1.0),
    color_end=(0.4, 0.0, 0.0, 0.0),
    shape=SHAPE_CIRCLE,
    additive=False,
)

DUST = ParticlePreset(
    count=10, speed_min=5, speed_max=25,
    angle=270, spread=60,
    gravity=-5, drag=3.0,
    life_min=0.5, life_max=1.5,
    size_start=3, size_end=6,
    color_start=(0.7, 0.6, 0.5, 0.3),
    color_end=(0.6, 0.5, 0.4, 0.0),
    shape=SHAPE_SOFT_DOT,
    additive=False,
    fade_in=0.3,
)

STEAM = ParticlePreset(
    count=6, speed_min=15, speed_max=40,
    angle=270, spread=20,
    gravity=-25, drag=1.5,
    life_min=0.6, life_max=1.5,
    size_start=6, size_end=20,
    color_start=(0.9, 0.9, 0.95, 0.3),
    color_end=(0.95, 0.95, 1.0, 0.0),
    shape=SHAPE_SOFT_DOT,
    additive=False,
    fade_in=0.25,
)


# ---------------------------------------------------------------------------
# Internal pool  (SoA layout for vectorised update)
# ---------------------------------------------------------------------------

class _ParticlePool:
    __slots__ = (
        "capacity", "count",
        "x", "y", "vx", "vy", "grav", "drag",
        "age", "lifetime",
        "size_s", "size_e",
        "rs", "gs", "bs", "a_s",
        "re", "ge", "be", "ae",
        "shape", "stretch",
        "alive", "additive",
        "_free",
        # New arrays
        "intensity", "vel_stretch", "fade_in",
        "spin", "rotation",
        "size_pulse_freq", "size_pulse_amp",
        "param1", "param2",
        "rm", "gm", "bm", "am", "color_mid_t", "has_mid_color",
        "on_death_preset", "on_death_count",
    )

    def __init__(self, cap: int):
        self.capacity = cap
        self.count = 0
        z = lambda: np.zeros(cap, dtype="f4")
        self.x = z(); self.y = z()
        self.vx = z(); self.vy = z()
        self.grav = z(); self.drag = z()
        self.age = z(); self.lifetime = z()
        self.size_s = z(); self.size_e = z()
        self.rs = z(); self.gs = z(); self.bs = z(); self.a_s = z()
        self.re = z(); self.ge = z(); self.be = z(); self.ae = z()
        self.shape = z(); self.stretch = z()
        self.alive = np.zeros(cap, dtype="bool")
        self.additive = np.zeros(cap, dtype="bool")
        self._free: list[int] = list(range(cap - 1, -1, -1))
        # New
        self.intensity = z(); self.vel_stretch = z(); self.fade_in = z()
        self.spin = z(); self.rotation = z()
        self.size_pulse_freq = z(); self.size_pulse_amp = z()
        self.param1 = z(); self.param2 = z()
        self.rm = z(); self.gm = z(); self.bm = z(); self.am = z()
        self.color_mid_t = z()
        self.has_mid_color = np.zeros(cap, dtype="bool")
        self.on_death_preset = np.empty(cap, dtype=object)
        self.on_death_count = np.zeros(cap, dtype="i4")


# ---------------------------------------------------------------------------
# Particle system
# ---------------------------------------------------------------------------

MAX_PARTICLES_DEFAULT = 4096
_FLOATS_PER_VERT = 12          # pos(2) + uv(2) + color(4) + data(4)
_VERTS_PER_QUAD = 4
_FPQ = _FLOATS_PER_VERT * _VERTS_PER_QUAD   # 48 floats per particle


class ParticleSystem:
    """GPU-batched 2D particle system with procedural SDF shapes.

    Usage::

        ps = ParticleSystem(ctx, max_particles=4096)

        # burst
        ps.emit(x, y, MY_PRESET)

        # each frame
        ps.update(dt)
        ps.render(projection_bytes)  # during scene pass

        # optional: feed lights to LightingSystem
        for lx, ly, lr, lc, li in ps.get_pending_lights():
            lighting.add(lx, ly, lr, lc, li)
    """

    def __init__(self, ctx: moderngl.Context, max_particles: int = MAX_PARTICLES_DEFAULT):
        self.ctx = ctx
        self.max = max_particles
        self._pool = _ParticlePool(max_particles)

        # Shader (self-contained, like FogLayer)
        self._prog = ctx.program(
            vertex_shader=load_shader("particle.vert"),
            fragment_shader=load_shader("particle.frag"),
        )

        # VBO  (dynamic, reused each frame)
        self._vd = np.zeros(max_particles * _FPQ, dtype="f4")
        self._vbo = ctx.buffer(reserve=self._vd.nbytes, dynamic=True)

        # Static IBO  (2 tris per quad)
        idx = np.empty(max_particles * 6, dtype="i4")
        bases = np.arange(max_particles, dtype="i4") * 4
        idx[0::6] = bases
        idx[1::6] = bases + 1
        idx[2::6] = bases + 2
        idx[3::6] = bases + 2
        idx[4::6] = bases + 3
        idx[5::6] = bases
        self._ibo = ctx.buffer(idx.tobytes())

        self._vao = ctx.vertex_array(
            self._prog,
            [(self._vbo, "2f 2f 4f 4f",
              "in_position", "in_uv", "in_color", "in_data")],
            index_buffer=self._ibo,
        )

        # Light emissions pending this frame
        self._lights: list[tuple] = []

        # Continuous emitters
        self._emitters: list[dict] = []

    # ------------------------------------------------------------------
    # Emission
    # ------------------------------------------------------------------

    def get_particle_count(self) -> int:
        """Ritorna il numero di particelle attive."""
        return self._pool.count

    def is_full(self) -> bool:
        """True se il pool di particelle e' pieno."""
        return len(self._pool._free) == 0

    def clear_all_particles(self) -> None:
        """Uccide tutte le particelle immediatamente."""
        pool = self._pool
        pool.alive[:] = False
        pool.count = 0
        pool._free = list(range(pool.capacity - 1, -1, -1))

    def clear_emitters(self) -> None:
        """Ferma tutti gli emitter continui."""
        self._emitters.clear()

    def is_emitter_active(self, emitter_id: str) -> bool:
        """True se l'emitter con questo ID e' attivo."""
        for e in self._emitters:
            if e["id"] == emitter_id:
                return e["active"]
        return False

    def emit(self, x: float, y: float, preset: ParticlePreset,
             angle_override: float | None = None) -> None:
        """Emit a burst of particles at world position (*x*, *y*)."""
        pool = self._pool
        n = min(preset.count, len(pool._free))
        if n == 0:
            return

        base_angle = angle_override if angle_override is not None else preset.angle

        # Pre-generate random values in bulk
        angles = np.radians(
            base_angle + np.random.uniform(-preset.spread, preset.spread, n).astype("f4")
        )
        speeds = np.random.uniform(preset.speed_min, preset.speed_max, n).astype("f4")
        lifetimes = np.random.uniform(preset.life_min, preset.life_max, n).astype("f4")

        # Pop indices from free list
        indices = np.array(pool._free[-n:], dtype="i4")
        del pool._free[-n:]

        pool.alive[indices] = True
        pool.count += n

        # --- Emission shape offset ---
        es = preset.emit_shape
        if es == "ring" and preset.emit_radius > 0:
            ea = np.random.uniform(0, 2 * math.pi, n).astype("f4")
            pool.x[indices] = x + np.cos(ea) * preset.emit_radius
            pool.y[indices] = y + np.sin(ea) * preset.emit_radius
        elif es == "line" and preset.emit_width > 0:
            t_line = np.random.uniform(-0.5, 0.5, n).astype("f4")
            rad = math.radians(preset.emit_angle)
            pool.x[indices] = x + t_line * preset.emit_width * math.cos(rad)
            pool.y[indices] = y + t_line * preset.emit_width * math.sin(rad)
        elif es == "rect" and (preset.emit_width > 0 or preset.emit_height > 0):
            pool.x[indices] = x + np.random.uniform(
                -preset.emit_width * 0.5, preset.emit_width * 0.5, n
            ).astype("f4")
            pool.y[indices] = y + np.random.uniform(
                -preset.emit_height * 0.5, preset.emit_height * 0.5, n
            ).astype("f4")
        else:
            pool.x[indices] = x
            pool.y[indices] = y

        pool.vx[indices] = np.cos(angles) * speeds
        pool.vy[indices] = np.sin(angles) * speeds
        pool.grav[indices] = preset.gravity
        pool.drag[indices] = preset.drag

        pool.age[indices] = 0.0
        pool.lifetime[indices] = lifetimes

        pool.size_s[indices] = preset.size_start
        pool.size_e[indices] = preset.size_end

        cs = preset.color_start
        ce = preset.color_end
        pool.rs[indices] = cs[0]; pool.gs[indices] = cs[1]
        pool.bs[indices] = cs[2]; pool.a_s[indices] = cs[3]
        pool.re[indices] = ce[0]; pool.ge[indices] = ce[1]
        pool.be[indices] = ce[2]; pool.ae[indices] = ce[3]

        pool.shape[indices] = float(preset.shape)
        pool.stretch[indices] = preset.spark_stretch
        pool.additive[indices] = preset.additive

        # --- New fields ---
        pool.intensity[indices] = preset.intensity
        pool.vel_stretch[indices] = preset.vel_stretch
        pool.fade_in[indices] = preset.fade_in

        # Spin: random angular velocity in range, random direction
        if preset.spin_min != 0.0 or preset.spin_max != 0.0:
            spin_rad = np.random.uniform(
                math.radians(preset.spin_min), math.radians(preset.spin_max), n
            ).astype("f4")
            spin_rad *= np.random.choice(np.array([-1.0, 1.0], dtype="f4"), n)
            pool.spin[indices] = spin_rad
        else:
            pool.spin[indices] = 0.0
        pool.rotation[indices] = 0.0

        pool.size_pulse_freq[indices] = preset.size_pulse_freq
        pool.size_pulse_amp[indices] = preset.size_pulse_amount

        # Shape-specific params
        if preset.shape == SHAPE_RING:
            pool.param1[indices] = preset.ring_thickness
        elif preset.shape == SHAPE_STAR:
            pool.param1[indices] = preset.star_inner_ratio
        else:
            pool.param1[indices] = 0.0
        pool.param2[indices] = float(preset.star_points) if preset.shape == SHAPE_STAR else 0.0

        # 3-stop colour
        if preset.color_mid is not None:
            cm = preset.color_mid
            pool.rm[indices] = cm[0]; pool.gm[indices] = cm[1]
            pool.bm[indices] = cm[2]; pool.am[indices] = cm[3]
            pool.color_mid_t[indices] = preset.color_mid_point
            pool.has_mid_color[indices] = True
        else:
            pool.has_mid_color[indices] = False

        # Sub-emitter
        pool.on_death_preset[indices] = preset.on_death
        pool.on_death_count[indices] = preset.on_death_count

        # Aggregate light
        if preset.emit_light:
            lc = preset.light_color or cs[:3]
            self._lights.append((x, y, preset.light_radius, lc, preset.light_intensity))

    def emit_continuous(self, emitter_id: str, x: float, y: float,
                        preset: ParticlePreset) -> None:
        """Register / update a continuous emitter (call every frame with current pos)."""
        for e in self._emitters:
            if e["id"] == emitter_id:
                e["x"], e["y"], e["preset"], e["active"] = x, y, preset, True
                return
        self._emitters.append({
            "id": emitter_id, "x": x, "y": y,
            "preset": preset, "acc": 0.0, "active": True,
        })

    def stop_emitter(self, emitter_id: str) -> None:
        """Stop a continuous emitter.  Existing particles keep living."""
        self._emitters = [e for e in self._emitters if e["id"] != emitter_id]

    # ------------------------------------------------------------------
    # Update  (vectorised)
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        pool = self._pool
        alive = pool.alive

        if np.any(alive):
            # Age
            pool.age[alive] += dt

            # Kill expired
            expired = alive & (pool.age >= pool.lifetime)
            if np.any(expired):
                idx_e = np.where(expired)[0]

                # Sub-emitters: spawn children at death positions
                for i in idx_e:
                    death_preset = pool.on_death_preset[i]
                    if death_preset is not None:
                        child = replace(death_preset,
                                        count=int(pool.on_death_count[i]),
                                        on_death=None, emit_light=False)
                        self.emit(float(pool.x[i]), float(pool.y[i]), child)

                pool.alive[idx_e] = False
                pool._free.extend(idx_e.tolist())
                pool.count -= len(idx_e)

            # Recompute alive mask
            alive = pool.alive
            if np.any(alive):
                # Drag
                drag_f = (1.0 - pool.drag[alive] * dt).clip(0.0, 1.0)
                pool.vx[alive] *= drag_f
                pool.vy[alive] *= drag_f

                # Gravity
                pool.vy[alive] += pool.grav[alive] * dt

                # Position
                pool.x[alive] += pool.vx[alive] * dt
                pool.y[alive] += pool.vy[alive] * dt

                # Spin -> rotation
                pool.rotation[alive] += pool.spin[alive] * dt

        # Continuous emitters
        for e in self._emitters:
            if not e["active"]:
                continue
            p = e["preset"]
            e["acc"] += p.count * dt
            while e["acc"] >= 1.0:
                e["acc"] -= 1.0
                single = replace(p, count=1, emit_light=False, on_death=None)
                self.emit(e["x"], e["y"], single)

    # ------------------------------------------------------------------
    # Render  (vectorised quad building, single/double draw call)
    # ------------------------------------------------------------------

    def render(self, projection_bytes: bytes,
               cam_x: float = 0.0, cam_y: float = 0.0) -> None:
        pool = self._pool
        alive = pool.alive
        if not np.any(alive):
            return

        indices = np.where(alive)[0]

        # Sort indices: alpha-blended first (additive=False -> 0), additive second (-> 1)
        add_flags = pool.additive[indices]
        sort_order = np.argsort(add_flags, kind="stable")
        indices = indices[sort_order]
        add_flags = add_flags[sort_order]
        n = len(indices)
        n_alpha = int(np.sum(~add_flags))
        n_add = n - n_alpha

        # ---- interpolation ----
        t = np.clip(pool.age[indices] / np.maximum(pool.lifetime[indices], 1e-4), 0.0, 1.0)
        t1 = 1.0 - t

        # --- Size ---
        size = pool.size_s[indices] * t1 + pool.size_e[indices] * t

        # Size pulse
        freq = pool.size_pulse_freq[indices]
        has_pulse = freq > 0.0
        if np.any(has_pulse):
            pulse = np.sin(pool.age[indices] * freq * 2.0 * math.pi) * pool.size_pulse_amp[indices]
            size = np.where(has_pulse, size + pulse, size)
        size = np.maximum(size, 0.5)

        # --- Colour ---
        has_mid = pool.has_mid_color[indices]
        if np.any(has_mid):
            mid_t = pool.color_mid_t[indices]
            mid_t_safe = np.maximum(mid_t, 1e-4)
            one_minus_mid_safe = np.maximum(1.0 - mid_t, 1e-4)
            t_before = np.clip(t / mid_t_safe, 0.0, 1.0)
            t_after = np.clip((t - mid_t) / one_minus_mid_safe, 0.0, 1.0)
            is_before = t < mid_t

            # 3-stop: start -> mid -> end
            r_3s = np.where(is_before,
                            pool.rs[indices] * (1 - t_before) + pool.rm[indices] * t_before,
                            pool.rm[indices] * (1 - t_after) + pool.re[indices] * t_after)
            g_3s = np.where(is_before,
                            pool.gs[indices] * (1 - t_before) + pool.gm[indices] * t_before,
                            pool.gm[indices] * (1 - t_after) + pool.ge[indices] * t_after)
            b_3s = np.where(is_before,
                            pool.bs[indices] * (1 - t_before) + pool.bm[indices] * t_before,
                            pool.bm[indices] * (1 - t_after) + pool.be[indices] * t_after)
            a_3s = np.where(is_before,
                            pool.a_s[indices] * (1 - t_before) + pool.am[indices] * t_before,
                            pool.am[indices] * (1 - t_after) + pool.ae[indices] * t_after)

            # 2-stop fallback
            r_2s = pool.rs[indices] * t1 + pool.re[indices] * t
            g_2s = pool.gs[indices] * t1 + pool.ge[indices] * t
            b_2s = pool.bs[indices] * t1 + pool.be[indices] * t
            a_2s = pool.a_s[indices] * t1 + pool.ae[indices] * t

            r = np.where(has_mid, r_3s, r_2s)
            g = np.where(has_mid, g_3s, g_2s)
            b = np.where(has_mid, b_3s, b_2s)
            a = np.where(has_mid, a_3s, a_2s)
        else:
            r = pool.rs[indices] * t1 + pool.re[indices] * t
            g = pool.gs[indices] * t1 + pool.ge[indices] * t
            b = pool.bs[indices] * t1 + pool.be[indices] * t
            a = pool.a_s[indices] * t1 + pool.ae[indices] * t

        # Fade-in
        fade_in_frac = pool.fade_in[indices]
        has_fade = fade_in_frac > 0.0
        if np.any(has_fade):
            fade_alpha = np.where(has_fade & (t < fade_in_frac),
                                  t / np.maximum(fade_in_frac, 1e-4),
                                  1.0)
            a = a * fade_alpha

        # HDR intensity
        intensity = pool.intensity[indices]
        r = r * intensity
        g = g * intensity
        b = b * intensity

        sh = pool.shape[indices]
        st = pool.stretch[indices]

        # world -> screen: apply camera offset
        sx = pool.x[indices] - cam_x
        sy = pool.y[indices] - cam_y

        # velocity direction (for spark/vel_stretch orientation)
        vxr = pool.vx[indices]
        vyr = pool.vy[indices]
        vlen = np.sqrt(vxr * vxr + vyr * vyr)
        vlen_safe = np.maximum(vlen, 1e-4)
        dx = vxr / vlen_safe
        dy = vyr / vlen_safe
        px = -dy   # perpendicular
        py = dx

        # ---- build quads ----
        vd = self._vd

        # Determine velocity-aligned particles (spark or vel_stretch > 0)
        vel_str = pool.vel_stretch[indices]
        is_spark = sh > 1.5
        is_spark &= sh < 2.5  # only shape 2
        is_vel_stretched = (vel_str > 0.0) | is_spark

        # Effective stretch factor
        eff_stretch = np.where(is_spark, st, vel_str)

        half = size * 0.5

        # Axis-aligned corners (non-velocity-stretched)
        x0 = sx - half;  x1 = sx + half
        y0 = sy - half;  y1 = sy + half

        # Velocity-aligned corners
        hw = size * eff_stretch * 0.5
        hh = size * 0.3
        d_hw_x = dx * hw;  d_hw_y = dy * hw
        p_hh_x = px * hh;  p_hh_y = py * hh

        # Per-particle corner selection
        bl_x = np.where(is_vel_stretched, sx - d_hw_x - p_hh_x, x0)
        bl_y = np.where(is_vel_stretched, sy - d_hw_y - p_hh_y, y1)
        br_x = np.where(is_vel_stretched, sx + d_hw_x - p_hh_x, x1)
        br_y = np.where(is_vel_stretched, sy + d_hw_y - p_hh_y, y1)
        tr_x = np.where(is_vel_stretched, sx + d_hw_x + p_hh_x, x1)
        tr_y = np.where(is_vel_stretched, sy + d_hw_y + p_hh_y, y0)
        tl_x = np.where(is_vel_stretched, sx - d_hw_x + p_hh_x, x0)
        tl_y = np.where(is_vel_stretched, sy - d_hw_y + p_hh_y, y0)

        # Spin rotation (non-velocity-stretched only)
        rot = pool.rotation[indices]
        has_rot = (rot != 0.0) & ~is_vel_stretched
        if np.any(has_rot):
            cos_r = np.cos(rot)
            sin_r = np.sin(rot)
            for corners in [(bl_x, bl_y), (br_x, br_y), (tr_x, tr_y), (tl_x, tl_y)]:
                cx_ = corners[0]
                cy_ = corners[1]
                dx_ = cx_ - sx
                dy_ = cy_ - sy
                corners[0][:] = np.where(has_rot, sx + dx_ * cos_r - dy_ * sin_r, cx_)
                corners[1][:] = np.where(has_rot, sy + dx_ * sin_r + dy_ * cos_r, cy_)

        # Data channel: shape, param1, param2, 0
        d0 = sh
        d1 = pool.param1[indices]
        d2 = pool.param2[indices]
        dz = np.zeros(n, dtype="f4")

        # Write interleaved vertex data  (12 floats x 4 verts = 48 per particle)
        base = np.arange(n) * _FPQ
        uv0 = np.zeros(n, dtype="f4")
        uv1 = np.ones(n, dtype="f4")

        for vi, (cx_, cy_, u, v) in enumerate([
            (bl_x, bl_y, uv0, uv0),   # BL  uv(0,0)
            (br_x, br_y, uv1, uv0),   # BR  uv(1,0)
            (tr_x, tr_y, uv1, uv1),   # TR  uv(1,1)
            (tl_x, tl_y, uv0, uv1),   # TL  uv(0,1)
        ]):
            off = base + vi * _FLOATS_PER_VERT
            vd[off]      = cx_
            vd[off + 1]  = cy_
            vd[off + 2]  = u
            vd[off + 3]  = v
            vd[off + 4]  = r
            vd[off + 5]  = g
            vd[off + 6]  = b
            vd[off + 7]  = a
            vd[off + 8]  = d0
            vd[off + 9]  = d1
            vd[off + 10] = d2
            vd[off + 11] = dz

        # ---- upload & draw ----
        self._prog["u_projection"].write(projection_bytes)
        total_floats = n * _FPQ
        self._vbo.write(vd[:total_floats].tobytes())

        from pyluxel.debug.gpu_stats import GPUStats

        if n_alpha > 0 and n_add > 0:
            # Both blend modes: alpha first, then additive
            self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
            self._vao.render(moderngl.TRIANGLES, vertices=n_alpha * 6)
            GPUStats.record_draw(n_alpha)

            self.ctx.blend_func = moderngl.ONE, moderngl.ONE
            self._vao.render(moderngl.TRIANGLES, vertices=n_add * 6,
                             first=n_alpha * 6)
            GPUStats.record_draw(n_add)
            self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

        elif n_add > 0:
            self.ctx.blend_func = moderngl.ONE, moderngl.ONE
            self._vao.render(moderngl.TRIANGLES, vertices=n * 6)
            GPUStats.record_draw(n)
            self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

        else:
            self._vao.render(moderngl.TRIANGLES, vertices=n * 6)
            GPUStats.record_draw(n)

    # ------------------------------------------------------------------
    # Light integration
    # ------------------------------------------------------------------

    def get_pending_lights(self) -> list[tuple]:
        """Return and clear pending light emissions from this frame.

        Each entry: ``(x, y, radius, color_tuple, intensity)``
        """
        lights = self._lights
        self._lights = []
        return lights

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def release(self) -> None:
        """Free GPU resources."""
        for obj in (self._vao, self._vbo, self._ibo, self._prog):
            try:
                obj.release()
            except Exception as e:
                cprint.warning("GPU release failed:", e)
