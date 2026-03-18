"""pyluxel.animation -- Sistema di animazione scheletrica per stickman."""

from pyluxel.animation.bone import Bone, Skeleton
from pyluxel.animation.animator import Pose, Animation, LoopMode, Animator
from pyluxel.animation.stickman import BoneVisual, EyeConfig, StickmanConfig, Stickman
from pyluxel.animation.state_machine import AnimStateMachine
from pyluxel.animation.presets import (
    create_default_skeleton,
    create_default_config,
    create_default_stickman,
    load_preset,
    IDLE, WALK, RUN, JUMP, FALL, LANDING, ATTACK,
)
from pyluxel.animation.model_io import (
    ModelData,
    save_model, load_model, export_animation, build_animation,
    create_empty_model, model_from_defaults,
)

__all__ = [
    "Bone", "Skeleton",
    "Pose", "Animation", "LoopMode", "Animator",
    "BoneVisual", "EyeConfig", "StickmanConfig", "Stickman",
    "AnimStateMachine",
    "create_default_skeleton", "create_default_config", "create_default_stickman",
    "load_preset",
    "IDLE", "WALK", "RUN", "JUMP", "FALL", "LANDING", "ATTACK",
    "ModelData", "save_model", "load_model", "export_animation", "build_animation",
    "create_empty_model", "model_from_defaults",
]
