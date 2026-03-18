"""Stickman platformer demo -- terrain, movement, jump, run, attack.

Controls:
    A / D  or  Arrows       Move
    Shift (hold)             Run
    Space                    Jump
    E / Left click           Attack
"""

import pygame
from pyluxel import App, Input, Mouse
from pyluxel.animation import (
    create_default_stickman, AnimStateMachine,
    IDLE, WALK, RUN, JUMP, FALL, LANDING, ATTACK,
)

# -- Game constants (design space 1280x720) --
GRAVITY = 1800.0
WALK_SPEED = 180.0
RUN_SPEED = 360.0
JUMP_FORCE = -620.0
BLEND = 0.15
LEG_HEIGHT = 27             # upper_leg(14) + lower_leg(13) after scale_lengths(0.5)
PLAYER_W = 10               # half bounding-box width
PLAYER_H = 100              # bounding-box height (feet -> head)

# Terrain: (x_left, y_surface, width, depth)
GROUND = [
    (0, 600, 1280, 120),      # floor
    (100, 510, 200, 20),      # left platform
    (520, 430, 240, 20),      # center platform
    (220, 330, 166, 20),      # mid platform
    (20, 230, 140, 20),
    (220, 130, 490, 20),
    (940, 510, 200, 20),      # right platform
]


class StickmanPlatformer(App):

    def setup(self):
        self.set_post_process(ambient=0.0, vignette=0.05, bloom=0.25, tone_mapping="none")
        self.light = self.add_light(640, 300, radius=600,
                                    color=(1.0, 0.95, 0.9), intensity=2.5,
                                    falloff=2)

        # -- Input bindings --
        Input.bind("left", pygame.K_a, pygame.K_LEFT)
        Input.bind("right", pygame.K_d, pygame.K_RIGHT)
        Input.bind("jump", pygame.K_SPACE, pygame.K_w, pygame.K_UP)
        Input.bind("sprint", pygame.K_LSHIFT, pygame.K_RSHIFT)
        Input.bind("attack", pygame.K_e, Mouse.LEFT)

        # -- Player --
        self.guy = create_default_stickman()
        self.guy.skeleton.scale_lengths(0.5)
        self.guy.set_head_radius(6)
        self.guy.set_eye_radius(1.0)
        self.guy.set_eye_spacing(2.0)
        self.guy.set_eye_offset(2.0, 0.5)
        self.guy.scale = 2

        self.px = 300.0
        self.py = 400.0
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self._jumped = False

        # -- Animation state machine --
        self.sm = AnimStateMachine(self.guy.animator)
        self.sm.add("idle", IDLE)
        self.sm.add("walk", WALK)
        self.sm.add("run", RUN)
        self.sm.add("jump", JUMP)
        self.sm.add("fall", FALL)
        self.sm.add("landing", LANDING)
        self.sm.add("attack", ATTACK, lock=True)
        self.sm.default = "idle"
        self.sm.set("idle")

        # Bone colors (cool tones for body, warm for legs)
        c = self.guy.config
        body = (0.85, 0.88, 0.92, 1.0)
        legs = (0.45, 0.50, 0.58, 1.0)
        for name in ("torso",):
            c.bone_visuals[name].bone_color = body
        for name in ("upper_arm_l", "lower_arm_l", "upper_arm_r", "lower_arm_r"):
            c.bone_visuals[name].bone_color = body
        for name in ("upper_leg_l", "lower_leg_l", "upper_leg_r", "lower_leg_r"):
            c.bone_visuals[name].bone_color = legs
        c.head_color = body

        self.ShowStats()

    # ------------------------------------------------------------------ update

    def update(self, dt):
        sm = self.sm

        # -- Horizontal input (blocked during attack) --
        move = 0.0
        if sm.state != "attack":
            if Input.held("left"):
                move = -1.0
            if Input.held("right"):
                move = 1.0

        sprinting = Input.held("sprint") and move != 0.0

        # Horizontal velocity
        target_speed = (RUN_SPEED if sprinting else WALK_SPEED) * move
        accel = 12.0 if self.on_ground else 5.0
        self.vx += (target_speed - self.vx) * min(accel * dt, 1.0)

        # -- Jump --
        if Input.pressed("jump") and self.on_ground and sm.state != "attack":
            self.vy = JUMP_FORCE
            self.on_ground = False
            self._jumped = True

        # -- Attack --
        if Input.pressed("attack") and self.on_ground:
            sm.set("attack", blend=BLEND)

        # -- Gravity --
        self.vy += GRAVITY * dt

        # -- Horizontal movement + X collision --
        self.px += self.vx * dt
        for gx, gy, gw, gh in GROUND:
            if (self.px + PLAYER_W > gx and self.px - PLAYER_W < gx + gw and
                    self.py > gy and self.py - PLAYER_H < gy + gh):
                if self.vx > 0:
                    self.px = gx - PLAYER_W
                elif self.vx < 0:
                    self.px = gx + gw + PLAYER_W
                self.vx = 0

        # -- Vertical movement + Y collision --
        self.py += self.vy * dt
        self.on_ground = False
        for gx, gy, gw, gh in GROUND:
            if (self.px + PLAYER_W > gx and self.px - PLAYER_W < gx + gw and
                    self.py > gy and self.py - PLAYER_H < gy + gh):
                if self.vy >= 0:
                    # Landing (from above)
                    self.py = gy
                    self.vy = 0
                    self.on_ground = True
                    self._jumped = False
                else:
                    # Head hitting ceiling (from below)
                    self.py = gy + gh + PLAYER_H
                    self.vy = 0

        # Side boundaries
        self.px = max(PLAYER_W, min(self.px, 1280 - PLAYER_W))

        # -- Flip based on direction --
        if move < 0:
            self.guy.flip_x = True
        elif move > 0:
            self.guy.flip_x = False

        # -- Animation state machine --
        if not self.on_ground:
            if self.vy < 0:
                sm.set("jump", blend=BLEND)
            elif self._jumped:
                sm.set("landing", blend=BLEND)
            else:
                sm.set("fall", blend=BLEND)
        elif abs(self.vx) > RUN_SPEED * 0.5:
            sm.set("run", blend=BLEND)
        elif abs(self.vx) > 20:
            sm.set("walk", blend=BLEND)
        else:
            sm.set("idle", blend=BLEND)

        self.light.x = self.px
        self.light.y = self.py
        self.guy.update(dt)

    # ------------------------------------------------------------------ draw

    def draw(self):
        # Background gradient
        self.draw_rect(0, 0, 1280, 360, r=0.08, g=0.06, b=0.14)
        self.draw_rect(0, 360, 1280, 360, r=0.04, g=0.03, b=0.08)

        # Terrain -- matches collision rectangles exactly
        for gx, gy, gw, gh in GROUND:
            self.draw_rect(gx, gy, gw, gh, r=0.15, g=0.25, b=0.15)
            self.draw_rect(gx, gy, gw, 3, r=0.35, g=0.55, b=0.35)

        # Stickman -- py is feet position, hip is higher up
        hip_y = self.py - LEG_HEIGHT * self.guy.scale
        self.guy.draw(self, self.px, hip_y)

    def draw_overlay(self):
        # Debug bounding box
        self.draw_rect(self.px - PLAYER_W, self.py - PLAYER_H,
                       PLAYER_W * 2, PLAYER_H, r=0.0, g=0.3, b=1.0, a=0.2)
        self.draw_circle(self.px, self.py, 4, r=0.0, g=0.3, b=1.0)

        label = self.sm.state.upper() or "..."
        if self.guy.animator.blending:
            label += " (blending)"
        self.draw_text(label, 640, 24, size=22, align_x="center", r=0.4, g=0.8, b=1.0)
        self.draw_text("A/D Move   Shift Run   Space Jump   E Attack",
                       640, 700, size=13, align_x="center", r=0.5, g=0.5, b=0.5)


StickmanPlatformer(1280, 720, "Stickman Platformer").run()
