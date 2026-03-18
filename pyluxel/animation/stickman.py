"""pyluxel.animation.stickman -- Rendering di stickman via forme geometriche."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from pyluxel.animation.bone import Skeleton
from pyluxel.animation.animator import Animation, Animator


@dataclass
class BoneVisual:
    """Configurazione visiva per una singola ossa."""
    draw_bone: bool = True
    draw_joint: bool = True
    bone_thickness: float = 6.0
    joint_radius: float = 4.0
    bone_color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    joint_color: tuple[float, float, float, float] = (0.9, 0.9, 0.9, 1.0)


@dataclass
class EyeConfig:
    """Configurazione degli occhi dello stickman (vista ~60 gradi).

    Entrambi gli occhi sono visibili ma spostati verso la direzione
    in cui il personaggio guarda, come se fosse girato di ~60 gradi.
    ``offset_x`` controlla quanto sono avanti, ``spacing`` la distanza
    tra i due occhi lungo la direzione della faccia.
    """
    enabled: bool = True
    radius: float = 2.0
    offset_x: float = 3.5
    spacing: float = 3.5
    offset_y: float = 1.0
    color: tuple[float, float, float, float] = (0.1, 0.1, 0.15, 1.0)


@dataclass
class StickmanConfig:
    """Configurazione di rendering per uno stickman.

    ``bone_visuals`` mappa nome osso -> BoneVisual. Le ossa non presenti
    usano ``default_visual``.
    """
    bone_visuals: dict[str, BoneVisual] = field(default_factory=dict)
    default_visual: BoneVisual = field(default_factory=BoneVisual)
    head_radius: float = 10.0
    head_color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    head_bone: str = "head"
    eyes: EyeConfig = field(default_factory=EyeConfig)

    def get_visual(self, bone_name: str) -> BoneVisual:
        return self.bone_visuals.get(bone_name, self.default_visual)


class Stickman:
    """Stickman animato: skeleton + animator + rendering.

    Uso tipico::

        guy = create_default_stickman()
        guy.play(IDLE)

        # nel game loop
        guy.update(dt)
        guy.draw(app, 400, 300)
    """

    def __init__(self, skeleton: Skeleton, config: StickmanConfig | None = None):
        self.skeleton = skeleton
        self.config = config or StickmanConfig()
        self.animator = Animator()
        self.flip_x: bool = False
        self.scale: float = 1.0

    # -- Animation shortcuts --

    def play(self, animation: Animation, speed: float = 1.0,
             on_complete=None, blend_time: float = 0.0) -> None:
        self.animator.play(animation, speed, on_complete, blend_time)

    def queue(self, animation: Animation, blend_time: float = 0.0) -> None:
        self.animator.queue(animation, blend_time)

    def stop(self) -> None:
        self.animator.stop()

    def set_head_radius(self, radius: float) -> None:
        """Imposta il raggio della testa."""
        self.config.head_radius = radius

    def set_head_color(self, r: float, g: float, b: float, a: float = 1.0) -> None:
        """Imposta il colore della testa."""
        self.config.head_color = (r, g, b, a)

    def set_eye_radius(self, radius: float) -> None:
        """Imposta il raggio degli occhi."""
        self.config.eyes.radius = radius

    def set_eye_color(self, r: float, g: float, b: float, a: float = 1.0) -> None:
        """Imposta il colore degli occhi."""
        self.config.eyes.color = (r, g, b, a)

    def set_eye_spacing(self, spacing: float) -> None:
        """Imposta la distanza tra i due occhi."""
        self.config.eyes.spacing = spacing

    def set_eye_offset(self, x: float, y: float) -> None:
        """Imposta l'offset degli occhi rispetto al centro della testa."""
        self.config.eyes.offset_x = x
        self.config.eyes.offset_y = y

    def set_eyes_enabled(self, enabled: bool) -> None:
        """Abilita o disabilita gli occhi."""
        self.config.eyes.enabled = enabled

    def update(self, dt: float) -> None:
        self.animator.update(dt)
        self.animator.apply(self.skeleton)

    # -- Drawing --

    def draw(self, app, x: float, y: float) -> None:
        """Risolve FK e disegna lo stickman nella posizione data.

        Parameters
        ----------
        app : App
            Istanza App con draw_circle e draw_capsule.
        x, y : float
            Posizione root (hip) in design space.
        """
        scale = self.scale
        ox, oy = self.animator.root_offset
        self.skeleton.solve(x + ox * scale, y + oy * scale, self.flip_x, scale)

        # Raccogliamo le ossa da disegnare (ordine depth-first)
        bones = []
        self._collect(self.skeleton.root, bones)

        # Pass 1: disegna ossa (capsule)
        for bone in bones:
            if bone.length <= 0:
                continue
            vis = self.config.get_visual(bone.name)
            if not vis.draw_bone:
                continue

            thickness = vis.bone_thickness * scale

            # Centro e lunghezza dalla posizione FK (gia' scalata)
            cx = (bone.world_x + bone.world_end_x) / 2
            cy = (bone.world_y + bone.world_end_y) / 2
            # Allungo di thickness cosi' le estremita' rotonde si sovrappongono
            length = bone.length * scale + thickness

            bc = vis.bone_color
            app.draw_capsule(cx, cy, length, thickness,
                             r=bc[0], g=bc[1], b=bc[2], a=bc[3],
                             angle=bone.world_angle_rad)

        # Pass 2: disegna giunture (cerchi) sopra le ossa
        for bone in bones:
            vis = self.config.get_visual(bone.name)
            if not vis.draw_joint:
                continue
            if vis.joint_radius <= 0:
                continue

            radius = vis.joint_radius * scale
            jc = vis.joint_color
            app.draw_circle(bone.world_x, bone.world_y, radius,
                            r=jc[0], g=jc[1], b=jc[2], a=jc[3])

        # Pass 3: testa + occhi
        head = self.skeleton.get(self.config.head_bone)
        if head is not None:
            hx = head.world_end_x
            hy = head.world_end_y
            hc = self.config.head_color
            hr = self.config.head_radius * scale
            app.draw_circle(hx, hy, hr,
                            r=hc[0], g=hc[1], b=hc[2], a=hc[3])

            eyes = self.config.eyes
            if eyes.enabled:
                # Direzione del bone testa e perpendicolare
                dx = math.cos(head.world_angle_rad)
                dy = math.sin(head.world_angle_rad)
                # Direzione "avanti" (verso la faccia): dipende da flip_x
                facing = -1.0 if self.flip_x else 1.0
                fx = -dy * facing
                fy = dx * facing

                # Base: centro spostato avanti + verso il corpo
                bx = hx + eyes.offset_x * fx * scale - eyes.offset_y * dx * scale
                by = hy + eyes.offset_x * fy * scale - eyes.offset_y * dy * scale
                sp = eyes.spacing * scale
                er = eyes.radius * scale
                ec = eyes.color

                # Occhio davanti (piu' esterno) e dietro (piu' interno)
                app.draw_circle(bx + sp * fx, by + sp * fy, er,
                                r=ec[0], g=ec[1], b=ec[2], a=ec[3])
                app.draw_circle(bx - sp * fx, by - sp * fy, er,
                                r=ec[0], g=ec[1], b=ec[2], a=ec[3])

    def _collect(self, bone, out: list) -> None:
        out.append(bone)
        for child in bone.children:
            self._collect(child, out)
