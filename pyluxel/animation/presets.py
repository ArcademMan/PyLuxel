"""pyluxel.animation.presets -- Stickman default e animazioni preset.

Le 5 animazioni preset (idle, walk, run, jump, attack) vengono caricate
da file JSON nella cartella ``pyluxel/animation/anims/``.
"""

from __future__ import annotations

import json
from importlib import resources

from pyluxel.animation.bone import Bone, Skeleton
from pyluxel.animation.animator import Animation, Pose, LoopMode
from pyluxel.animation.stickman import Stickman, StickmanConfig, BoneVisual


def create_default_skeleton() -> Skeleton:
    """Crea lo scheletro umanoide default (11 ossa).

    Gerarchia::

        hip (root, length=0)
          +-- torso (40px, punta SU)
          |     +-- head (16px, continua su)
          |     +-- upper_arm_l (24px) -> lower_arm_l (22px)
          |     +-- upper_arm_r (24px) -> lower_arm_r (22px)
          +-- upper_leg_l (28px) -> lower_leg_l (26px)
          +-- upper_leg_r (28px) -> lower_leg_r (26px)

    Angoli default: T-pose. Le animazioni sovrascrivono gli angoli.
    """
    hip = Bone("hip", length=0)

    torso = hip.add_child(Bone("torso", length=40, local_angle=0))
    torso.add_child(Bone("head", length=8, local_angle=0))

    upper_arm_l = torso.add_child(Bone("upper_arm_l", length=24, local_angle=-90))
    upper_arm_l.add_child(Bone("lower_arm_l", length=22, local_angle=0))

    upper_arm_r = torso.add_child(Bone("upper_arm_r", length=24, local_angle=90))
    upper_arm_r.add_child(Bone("lower_arm_r", length=22, local_angle=0))

    upper_leg_l = hip.add_child(Bone("upper_leg_l", length=28, local_angle=180))
    upper_leg_l.add_child(Bone("lower_leg_l", length=26, local_angle=0))

    upper_leg_r = hip.add_child(Bone("upper_leg_r", length=28, local_angle=180))
    upper_leg_r.add_child(Bone("lower_leg_r", length=26, local_angle=0))

    return Skeleton(hip)


def create_default_config() -> StickmanConfig:
    """Configurazione visiva default: stick figure bianco."""
    body = (1.0, 1.0, 1.0, 1.0)

    visuals = {
        "hip": BoneVisual(draw_bone=False, draw_joint=False),
        "torso": BoneVisual(bone_thickness=5, draw_joint=False, bone_color=body),
        "head": BoneVisual(draw_bone=False, draw_joint=False),
        "upper_arm_l": BoneVisual(bone_thickness=4, draw_joint=False, bone_color=body),
        "lower_arm_l": BoneVisual(bone_thickness=4, draw_joint=False, bone_color=body),
        "upper_arm_r": BoneVisual(bone_thickness=4, draw_joint=False, bone_color=body),
        "lower_arm_r": BoneVisual(bone_thickness=4, draw_joint=False, bone_color=body),
        "upper_leg_l": BoneVisual(bone_thickness=4, draw_joint=False, bone_color=body),
        "lower_leg_l": BoneVisual(bone_thickness=4, draw_joint=False, bone_color=body),
        "upper_leg_r": BoneVisual(bone_thickness=4, draw_joint=False, bone_color=body),
        "lower_leg_r": BoneVisual(bone_thickness=4, draw_joint=False, bone_color=body),
    }

    return StickmanConfig(
        bone_visuals=visuals,
        head_radius=12,
        head_color=body,
        head_bone="head",
    )


def create_default_stickman() -> Stickman:
    """Crea uno Stickman con scheletro e config default, pronto all'uso."""
    return Stickman(create_default_skeleton(), create_default_config())


# -------------------------------------------------------------------------
# Loader JSON per animazioni preset
# -------------------------------------------------------------------------

def _load_anim_json(name: str) -> Animation:
    """Carica un'animazione preset dal JSON in pyluxel.animation.anims."""
    ref = resources.files("pyluxel.animation.anims").joinpath(f"{name}.json")
    raw = ref.read_text(encoding="utf-8")
    data = json.loads(raw)
    kfs = tuple(
        (kf["time"], Pose(kf["angles"],
                          kf.get("offset_x", 0.0),
                          kf.get("offset_y", 0.0)))
        for kf in data["keyframes"]
    )
    duration = data.get("duration", kfs[-1][0] if kfs else 1.0)
    return Animation(
        name=data["name"],
        keyframes=kfs,
        loop_mode=LoopMode[data["loop_mode"]],
        duration=duration,
    )


def load_preset(name: str) -> Animation:
    """Carica un'animazione preset per nome dalla cartella anims/.

    Nomi disponibili: ``idle``, ``walk``, ``run``, ``jump``, ``fall``, ``landing``, ``attack``
    (o qualsiasi JSON aggiunto alla cartella).
    """
    return _load_anim_json(name)


# -------------------------------------------------------------------------
# Preset globali (caricati al primo import)
# -------------------------------------------------------------------------

IDLE = _load_anim_json("idle")
WALK = _load_anim_json("walk")
RUN = _load_anim_json("run")
JUMP = _load_anim_json("jump")
FALL = _load_anim_json("fall")
LANDING = _load_anim_json("landing")
ATTACK = _load_anim_json("attack")
