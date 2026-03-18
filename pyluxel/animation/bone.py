"""pyluxel.animation.bone -- Gerarchia ossa e forward kinematics."""

from __future__ import annotations

import math


class Bone:
    """Singola ossa con angolo locale relativo al parent.

    Angoli in **gradi** (local_angle). Le coordinate mondo vengono
    calcolate da ``Skeleton.solve()``.
    """

    __slots__ = (
        "name", "length", "local_angle",
        "parent", "children",
        "world_x", "world_y",
        "world_end_x", "world_end_y",
        "world_angle_rad",
    )

    def __init__(self, name: str, length: float = 0.0,
                 local_angle: float = 0.0):
        self.name = name
        self.length = length
        self.local_angle = local_angle  # gradi, relativo al parent

        self.parent: Bone | None = None
        self.children: list[Bone] = []

        # Calcolati da solve()
        self.world_x = 0.0
        self.world_y = 0.0
        self.world_end_x = 0.0
        self.world_end_y = 0.0
        self.world_angle_rad = 0.0

    def add_child(self, bone: Bone) -> Bone:
        """Aggiunge un figlio e ritorna il figlio (per chaining)."""
        bone.parent = self
        self.children.append(bone)
        return bone

    def remove_child(self, bone: Bone) -> bool:
        """Rimuove un figlio. Ritorna True se trovato."""
        try:
            self.children.remove(bone)
            bone.parent = None
            return True
        except ValueError:
            return False


class Skeleton:
    """Albero di ossa con forward kinematics.

    Costruisci la gerarchia aggiungendo figli alla root, poi chiama
    ``solve(x, y)`` per calcolare le posizioni mondo.
    """

    def __init__(self, root: Bone):
        self.root = root
        self._lookup: dict[str, Bone] = {}
        self._rebuild_lookup()

    def _rebuild_lookup(self) -> None:
        self._lookup.clear()
        self._walk(self.root)

    def _walk(self, bone: Bone) -> None:
        self._lookup[bone.name] = bone
        for child in bone.children:
            self._walk(child)

    def get(self, name: str) -> Bone | None:
        """Ritorna l'osso per nome, o None."""
        return self._lookup.get(name)

    def has_bone(self, name: str) -> bool:
        """True se l'osso esiste nello scheletro."""
        return name in self._lookup

    def remove_bone(self, name: str) -> bool:
        """Rimuove un osso dalla gerarchia. Ritorna True se trovato."""
        bone = self._lookup.get(name)
        if bone is None or bone is self.root:
            return False
        if bone.parent:
            bone.parent.remove_child(bone)
        self._rebuild_lookup()
        return True

    @property
    def bone_names(self) -> list[str]:
        return list(self._lookup.keys())

    def solve(self, root_x: float, root_y: float,
              flip_x: bool = False, scale: float = 1.0) -> None:
        """Forward kinematics: calcola posizioni mondo di tutte le ossa.

        Parameters
        ----------
        root_x, root_y : float
            Posizione della root (es. hip) in design space.
        flip_x : bool
            Se True, specchia orizzontalmente lo scheletro.
        scale : float
            Scala le lunghezze delle ossa per il calcolo delle posizioni.
        """
        self._solve_bone(self.root, root_x, root_y, -90.0, flip_x, scale)

    def _solve_bone(self, bone: Bone, px: float, py: float,
                    parent_angle_deg: float, flip_x: bool,
                    scale: float) -> None:
        bone.world_x = px
        bone.world_y = py

        # Angolo "raw" (non flippato) nella catena
        raw_angle = parent_angle_deg + bone.local_angle

        if flip_x:
            angle_deg = 180.0 - raw_angle
        else:
            angle_deg = raw_angle

        bone.world_angle_rad = math.radians(angle_deg)

        scaled_length = bone.length * scale
        if scaled_length > 0:
            bone.world_end_x = px + math.cos(bone.world_angle_rad) * scaled_length
            bone.world_end_y = py + math.sin(bone.world_angle_rad) * scaled_length
        else:
            bone.world_end_x = px
            bone.world_end_y = py

        # Passa raw_angle ai figli (non flippato), il flip si applica ad ogni osso
        for child in bone.children:
            self._solve_bone(child, bone.world_end_x, bone.world_end_y,
                             raw_angle, flip_x, scale)

    def set_bone_length(self, name: str, length: float) -> None:
        """Imposta la lunghezza di un osso specifico.

        Parameters
        ----------
        name : str
            Nome dell'osso.
        length : float
            Nuova lunghezza in pixel (design space).
        """
        bone = self._lookup.get(name)
        if bone is not None:
            bone.length = length

    def scale_lengths(self, factor: float) -> None:
        """Scala la lunghezza di tutte le ossa per un fattore.

        Non tocca spessore ne' joint — solo le lunghezze.

        Parameters
        ----------
        factor : float
            Moltiplicatore (es. 0.5 = dimezza, 2.0 = raddoppia).
        """
        for bone in self._lookup.values():
            bone.length *= factor

    def rebuild(self) -> None:
        """Ricostruisce il lookup interno dopo modifiche strutturali."""
        self._rebuild_lookup()

    def clone(self) -> Skeleton:
        """Crea una copia profonda dello scheletro."""
        new_root = self._clone_bone(self.root)
        return Skeleton(new_root)

    def _clone_bone(self, bone: Bone) -> Bone:
        new_bone = Bone(bone.name, bone.length, bone.local_angle)
        for child in bone.children:
            new_bone.add_child(self._clone_bone(child))
        return new_bone
