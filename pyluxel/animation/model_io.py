"""pyluxel.animation.model_io -- Salvataggio e caricamento di modelli .model.json."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from pyluxel.animation.bone import Bone, Skeleton
from pyluxel.animation.animator import Animation, Pose, LoopMode
from pyluxel.animation.stickman import BoneVisual, EyeConfig, StickmanConfig, Stickman


@dataclass
class ModelData:
    """Rappresentazione in memoria di un modello completo."""
    name: str = "untitled"
    skeleton: Skeleton | None = None
    config: StickmanConfig | None = None
    rest_angles: dict[str, float] = field(default_factory=dict)
    # nome -> ([(norm_time, {bone: angle}), ...], LoopMode, duration)
    animations: dict[str, tuple[list, LoopMode, float]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Serializzazione
# ---------------------------------------------------------------------------

_BV_DEFAULTS = BoneVisual()


def _visual_to_dict(vis: BoneVisual) -> dict:
    """Serializza un BoneVisual in dict (tutti i campi)."""
    return {
        "draw_bone": vis.draw_bone,
        "draw_joint": vis.draw_joint,
        "bone_thickness": vis.bone_thickness,
        "joint_radius": vis.joint_radius,
        "bone_color": list(vis.bone_color),
        "joint_color": list(vis.joint_color),
    }


def _visual_diff(vis: BoneVisual, default: BoneVisual) -> dict:
    """Serializza solo i campi che differiscono dal default."""
    d: dict = {}
    if vis.draw_bone != default.draw_bone:
        d["draw_bone"] = vis.draw_bone
    if vis.draw_joint != default.draw_joint:
        d["draw_joint"] = vis.draw_joint
    if vis.bone_thickness != default.bone_thickness:
        d["bone_thickness"] = vis.bone_thickness
    if vis.joint_radius != default.joint_radius:
        d["joint_radius"] = vis.joint_radius
    if vis.bone_color != default.bone_color:
        d["bone_color"] = list(vis.bone_color)
    if vis.joint_color != default.joint_color:
        d["joint_color"] = list(vis.joint_color)
    return d


def _dict_to_visual(d: dict, default: BoneVisual) -> BoneVisual:
    """Ricostruisce un BoneVisual da dict, usando default per campi mancanti."""
    return BoneVisual(
        draw_bone=d.get("draw_bone", default.draw_bone),
        draw_joint=d.get("draw_joint", default.draw_joint),
        bone_thickness=d.get("bone_thickness", default.bone_thickness),
        joint_radius=d.get("joint_radius", default.joint_radius),
        bone_color=tuple(d.get("bone_color", default.bone_color)),
        joint_color=tuple(d.get("joint_color", default.joint_color)),
    )


def _collect_bones(bone: Bone, out: list) -> None:
    """Raccoglie ossa in ordine depth-first."""
    out.append(bone)
    for child in bone.children:
        _collect_bones(child, out)


def save_model(model: ModelData, path: str) -> None:
    """Salva un ModelData come .model.json."""
    skel = model.skeleton
    config = model.config or StickmanConfig()

    # Skeleton
    bones_list = []
    all_bones: list[Bone] = []
    _collect_bones(skel.root, all_bones)
    for bone in all_bones:
        bones_list.append({
            "name": bone.name,
            "length": round(bone.length, 2),
            "angle": round(model.rest_angles.get(bone.name, bone.local_angle), 2),
            "parent": bone.parent.name if bone.parent else None,
        })

    # Visuals
    default_vis = _visual_to_dict(config.default_visual)
    bone_vis = {}
    for name, vis in config.bone_visuals.items():
        diff = _visual_diff(vis, config.default_visual)
        if diff:
            bone_vis[name] = diff

    eyes_d = {
        "enabled": config.eyes.enabled,
        "radius": config.eyes.radius,
        "offset_x": config.eyes.offset_x,
        "spacing": config.eyes.spacing,
        "offset_y": config.eyes.offset_y,
        "color": list(config.eyes.color),
    }

    visuals = {
        "default": default_vis,
        "bones": bone_vis,
        "head_radius": config.head_radius,
        "head_color": list(config.head_color),
        "head_bone": config.head_bone,
        "eyes": eyes_d,
    }

    # Animations
    anims_d = {}
    for anim_name, (kfs, loop_mode, duration) in model.animations.items():
        kf_list = []
        for t, angles, *rest in kfs:
            kf_d = {"time": round(t, 4),
                    "angles": {k: round(v, 1) for k, v in angles.items()}}
            # rest puo' contenere (offset_x, offset_y) se presenti
            ox = rest[0] if len(rest) > 0 else 0.0
            oy = rest[1] if len(rest) > 1 else 0.0
            if ox or oy:
                kf_d["offset_x"] = round(ox, 2)
                kf_d["offset_y"] = round(oy, 2)
            kf_list.append(kf_d)
        anims_d[anim_name] = {
            "loop_mode": loop_mode.name,
            "duration": round(duration, 4),
            "keyframes": kf_list,
        }

    data = {
        "version": 1,
        "name": model.name,
        "skeleton": {"root": skel.root.name, "bones": bones_list},
        "visuals": visuals,
        "animations": anims_d,
    }

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_model(path: str) -> ModelData:
    """Carica un ModelData da .model.json."""
    with open(path) as f:
        data = json.load(f)

    # Skeleton
    bones_data = data["skeleton"]["bones"]
    root_name = data["skeleton"]["root"]

    bone_map: dict[str, Bone] = {}
    rest_angles: dict[str, float] = {}

    # Prima passata: crea tutti i Bone
    for bd in bones_data:
        b = Bone(bd["name"], float(bd["length"]), float(bd["angle"]))
        bone_map[b.name] = b
        rest_angles[b.name] = float(bd["angle"])

    # Seconda passata: collega parent/children
    for bd in bones_data:
        parent_name = bd.get("parent")
        if parent_name and parent_name in bone_map:
            bone_map[parent_name].add_child(bone_map[bd["name"]])

    skeleton = Skeleton(bone_map[root_name])

    # Visuals
    vis_data = data.get("visuals", {})
    default_vis = _dict_to_visual(vis_data.get("default", {}), _BV_DEFAULTS)

    bone_visuals = {}
    for name, vd in vis_data.get("bones", {}).items():
        bone_visuals[name] = _dict_to_visual(vd, default_vis)

    eyes_d = vis_data.get("eyes", {})
    eyes = EyeConfig(
        enabled=eyes_d.get("enabled", True),
        radius=eyes_d.get("radius", 2.0),
        offset_x=eyes_d.get("offset_x", 3.5),
        spacing=eyes_d.get("spacing", 3.5),
        offset_y=eyes_d.get("offset_y", 1.0),
        color=tuple(eyes_d.get("color", (0.1, 0.1, 0.15, 1.0))),
    )

    config = StickmanConfig(
        bone_visuals=bone_visuals,
        default_visual=default_vis,
        head_radius=vis_data.get("head_radius", 10.0),
        head_color=tuple(vis_data.get("head_color", (1.0, 1.0, 1.0, 1.0))),
        head_bone=vis_data.get("head_bone", "head"),
        eyes=eyes,
    )

    # Animations
    animations: dict[str, tuple[list, LoopMode, float]] = {}
    for anim_name, ad in data.get("animations", {}).items():
        loop_mode = LoopMode[ad["loop_mode"]]
        kfs = [(kf["time"], dict(kf["angles"]),
                 kf.get("offset_x", 0.0), kf.get("offset_y", 0.0))
                for kf in ad["keyframes"]]
        duration = ad.get("duration", kfs[-1][0] if kfs else 1.0)
        animations[anim_name] = (kfs, loop_mode, duration)

    return ModelData(
        name=data.get("name", "untitled"),
        skeleton=skeleton,
        config=config,
        rest_angles=rest_angles,
        animations=animations,
    )


def export_animation(name: str, keyframes: list, loop_mode: LoopMode,
                     path: str, duration: float = 1.0) -> None:
    """Esporta una singola animazione come .json (formato compatibile)."""
    kf_list = []
    for t, angles, *rest in keyframes:
        kf_d = {"time": round(t, 4),
                "angles": {k: round(v, 1) for k, v in angles.items()}}
        ox = rest[0] if len(rest) > 0 else 0.0
        oy = rest[1] if len(rest) > 1 else 0.0
        if ox or oy:
            kf_d["offset_x"] = round(ox, 2)
            kf_d["offset_y"] = round(oy, 2)
        kf_list.append(kf_d)
    data = {
        "name": name,
        "loop_mode": loop_mode.name,
        "duration": round(duration, 4),
        "keyframes": kf_list,
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def build_animation(name: str, keyframes: list, loop_mode: LoopMode,
                    duration: float = 1.0) -> Animation:
    """Converte keyframes editabili in un oggetto Animation frozen."""
    def _make_pose(entry):
        if len(entry) == 2:
            t, angles = entry
            return t, Pose(angles)
        t, angles, ox, oy = entry[0], entry[1], entry[2], entry[3]
        return t, Pose(angles, ox, oy)
    kfs = tuple(_make_pose(e) for e in keyframes)
    return Animation(name=name, keyframes=kfs, loop_mode=loop_mode, duration=duration)


def create_empty_model(name: str = "untitled") -> ModelData:
    """Crea un modello vuoto con solo un osso root."""
    root = Bone("root", length=0)
    skeleton = Skeleton(root)
    return ModelData(
        name=name,
        skeleton=skeleton,
        config=StickmanConfig(eyes=EyeConfig(enabled=False)),
        rest_angles={"root": 0},
        animations={},
    )


def model_from_defaults() -> ModelData:
    """Crea un ModelData dallo stickman default con i 5 preset."""
    from pyluxel.animation.presets import (
        create_default_skeleton, create_default_config,
        IDLE, WALK, RUN, JUMP, ATTACK,
    )

    skeleton = create_default_skeleton()
    config = create_default_config()

    # Cattura rest angles dallo scheletro
    rest: dict[str, float] = {}
    all_bones: list[Bone] = []
    _collect_bones(skeleton.root, all_bones)
    for bone in all_bones:
        rest[bone.name] = bone.local_angle

    # Converti animazioni preset in formato editabile
    def _anim_to_edit(anim: Animation) -> tuple[list, LoopMode, float]:
        kfs = []
        for t, p in anim.keyframes:
            if p.offset_x or p.offset_y:
                kfs.append((t, dict(p.angles), p.offset_x, p.offset_y))
            else:
                kfs.append((t, dict(p.angles)))
        return kfs, anim.loop_mode, anim.duration

    animations = {}
    for anim in (IDLE, WALK, RUN, JUMP, ATTACK):
        animations[anim.name] = _anim_to_edit(anim)

    return ModelData(
        name="stickman",
        skeleton=skeleton,
        config=config,
        rest_angles=rest,
        animations=animations,
    )
