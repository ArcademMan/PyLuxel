"""Configurazione degli effetti di post-processing."""
from __future__ import annotations

from dataclasses import dataclass, field, fields, asdict
from copy import copy
import moderngl

from pyluxel.debug import cprint


@dataclass
class PostFX:
    """Configurazione per tutti gli effetti di post-processing.

    I parametri a 0.0 o False sono disattivati e non hanno costo GPU.
    Passare un oggetto PostFX a ``renderer.post_process(fx)`` oppure
    usare ``app.fx`` per modificare i valori al volo.
    """

    # -- effetti esistenti (migliorati) --
    vignette: float = 2.0
    """Intensita' vignette radiale (0.0 = disattivata)."""

    bloom: float = 0.5
    """Intensita' bloom dual-kawase (0.0 = disattivato)."""

    tone_mapping: str = "aces"
    """Operatore di tone mapping: 'aces', 'reinhard', 'none'."""

    exposure: float = 1.0
    """Moltiplicatore di esposizione pre-tonemapping."""

    # -- nuovi effetti toggleable --
    chromatic_aberration: float = 0.0
    """Aberrazione cromatica ai bordi (0.0 = off, 0.3-1.0 consigliato)."""

    film_grain: float = 0.0
    """Intensita' del film grain animato (0.0 = off, 0.05-0.2 consigliato)."""

    crt: bool = False
    """Attiva effetto CRT (curvatura + scanlines)."""

    crt_curvature: float = 0.02
    """Quantita' di curvatura barrel per CRT."""

    crt_scanline: float = 0.3
    """Intensita' delle scanlines CRT."""

    color_grading_lut: moderngl.Texture | None = field(default=None, repr=False)
    """Texture LUT 32x32x32 (formato strip 1024x32) per color grading. None = off."""

    god_rays: float = 0.0
    """Intensita' god rays (0.0 = off, 0.3-0.8 consigliato)."""

    god_rays_x: float = 0.5
    """Posizione X sorgente god rays (0-1 in UV space, 0.5 = centro)."""

    god_rays_y: float = 0.0
    """Posizione Y sorgente god rays (0-1 in UV space, 0.0 = top)."""

    god_rays_decay: float = 0.96
    """Fattore di decadimento per sample (0.9-0.99)."""

    god_rays_density: float = 0.5
    """Densita' dei raggi (0.3-1.0)."""

    pixel_perfect: bool = False
    """Scaling della scena a schermo: True = NEAREST (pixel art nitido),
    False = LINEAR (smooth). Influenza solo la scena (combine FBO -> screen),
    l'HUD via begin_screen_overlay() renderizza sempre a risoluzione nativa
    e non e' influenzato da questa impostazione."""

    def set_vignette(self, strength: float):
        """Imposta intensita' vignette (0 = off)."""
        self.vignette = strength

    def set_bloom(self, intensity: float):
        """Imposta intensita' bloom (0 = off)."""
        self.bloom = intensity

    def set_tone_mapping(self, mode: str):
        """Imposta operatore tone mapping ('aces', 'reinhard', 'none')."""
        self.tone_mapping = mode

    def set_exposure(self, value: float):
        """Imposta moltiplicatore esposizione."""
        self.exposure = value

    def set_chromatic_aberration(self, intensity: float):
        """Imposta aberrazione cromatica (0 = off, 0.3-1.0 consigliato)."""
        self.chromatic_aberration = intensity

    def set_film_grain(self, intensity: float):
        """Imposta film grain (0 = off, 0.05-0.2 consigliato)."""
        self.film_grain = intensity

    def set_crt(self, enabled: bool, curvature: float = None,
                scanline: float = None):
        """Configura effetto CRT.

        Args:
            enabled: attiva/disattiva CRT
            curvature: curvatura barrel (default invariato)
            scanline: intensita' scanlines (default invariato)
        """
        self.crt = enabled
        if curvature is not None:
            self.crt_curvature = curvature
        if scanline is not None:
            self.crt_scanline = scanline

    def set_color_grading_lut(self, lut: moderngl.Texture | None):
        """Imposta texture LUT per color grading (None = off)."""
        self.color_grading_lut = lut

    def set_god_rays(self, intensity: float, x: float = None,
                     y: float = None, decay: float = None,
                     density: float = None):
        """Configura god rays.

        Args:
            intensity: intensita' (0 = off, 0.3-0.8 consigliato)
            x: posizione X sorgente UV (0-1)
            y: posizione Y sorgente UV (0-1)
            decay: decadimento per sample (0.9-0.99)
            density: densita' raggi (0.3-1.0)
        """
        self.god_rays = intensity
        if x is not None:
            self.god_rays_x = x
        if y is not None:
            self.god_rays_y = y
        if decay is not None:
            self.god_rays_decay = decay
        if density is not None:
            self.god_rays_density = density

    def set_pixel_perfect(self, enabled: bool):
        """Imposta lo scaling della scena a schermo.

        Quando abilitato usa NEAREST filtering (pixel perfetti, ideale per
        pixel art). Quando disabilitato usa LINEAR (scaling smooth).

        Non influenza l'HUD (begin_screen_overlay) che renderizza sempre
        direttamente a risoluzione nativa dello schermo.

        Args:
            enabled: True per NEAREST (pixel art), False per LINEAR (smooth).
        """
        self.pixel_perfect = enabled

    def reset(self):
        """Ripristina tutti gli effetti ai valori di default."""
        defaults = PostFX()
        for f in fields(self):
            setattr(self, f.name, getattr(defaults, f.name))

    def clone(self) -> PostFX:
        """Crea una copia indipendente della configurazione."""
        return copy(self)

    def get_state(self) -> dict:
        """Ritorna lo stato corrente come dizionario (esclude LUT texture)."""
        state = {}
        for f in fields(self):
            if f.name == "color_grading_lut":
                continue
            state[f.name] = getattr(self, f.name)
        return state

    def load_state(self, state: dict):
        """Ripristina lo stato da un dizionario (generato da get_state)."""
        for key, value in state.items():
            if key == "color_grading_lut":
                continue
            if hasattr(self, key):
                setattr(self, key, value)


class Shockwave:
    """Un singolo effetto di distorsione shockwave."""

    __slots__ = ("x", "y", "time", "duration", "max_radius", "thickness", "strength")

    def __init__(
        self,
        x: float,
        y: float,
        max_radius: float = 200.0,
        thickness: float = 30.0,
        strength: float = 0.05,
        duration: float = 0.0,
    ):
        self.x = x
        self.y = y
        self.time = 0.0
        self.duration = duration
        self.max_radius = max_radius
        self.thickness = thickness
        self.strength = strength

    def update(self, dt: float) -> None:
        self.time += dt

    @property
    def radius(self) -> float:
        """Raggio corrente dello shockwave."""
        return self.time * self.max_radius * 2.0

    def set_position(self, x: float, y: float):
        """Imposta la posizione dello shockwave."""
        self.x = x
        self.y = y

    def set_params(self, max_radius: float = None, thickness: float = None,
                   strength: float = None):
        """Aggiorna i parametri dello shockwave (solo quelli passati)."""
        if max_radius is not None:
            self.max_radius = max_radius
        if thickness is not None:
            self.thickness = thickness
        if strength is not None:
            self.strength = strength

    def is_alive(self) -> bool:
        return self.radius < self.max_radius


class ShockwaveManager:
    """Gestisce piu' shockwave attivi contemporaneamente."""

    MAX_SHOCKWAVES = 8

    def __init__(self) -> None:
        self.shockwaves: list[Shockwave] = []

    def add(
        self,
        x: float,
        y: float,
        max_radius: float = 200.0,
        thickness: float = 30.0,
        strength: float = 0.05,
    ) -> Shockwave:
        sw = Shockwave(x, y, max_radius, thickness, strength)
        self.shockwaves.append(sw)
        return sw

    def update(self, dt: float) -> None:
        for sw in self.shockwaves:
            sw.update(dt)
        self.shockwaves = [sw for sw in self.shockwaves if sw.is_alive()]

    def remove(self, shockwave: Shockwave) -> None:
        """Rimuovi un singolo shockwave."""
        try:
            self.shockwaves.remove(shockwave)
        except ValueError as e:
            cprint.warning(e)

    def get_count(self) -> int:
        """Ritorna il numero di shockwave attivi."""
        return len(self.shockwaves)

    def is_full(self) -> bool:
        """True se il buffer shockwave e' al massimo."""
        return len(self.shockwaves) >= self.MAX_SHOCKWAVES

    def clear(self) -> None:
        self.shockwaves.clear()


class HeatHaze:
    """Zona di distorsione persistente (calore, vapore, portali).

    A differenza dello shockwave, l'heat haze e' persistente e oscilla
    continuamente. Definisce un rettangolo in design space dove l'aria
    "trema".
    """

    __slots__ = ("x", "y", "width", "height", "strength", "speed", "scale")

    def __init__(self, x: float, y: float, width: float, height: float,
                 strength: float = 0.003, speed: float = 3.0, scale: float = 20.0):
        self.x = x
        """Posizione X del rettangolo (design space)."""
        self.y = y
        """Posizione Y del rettangolo (design space)."""
        self.width = width
        """Larghezza della zona di distorsione."""
        self.height = height
        """Altezza della zona di distorsione."""
        self.strength = strength
        """Intensita' della distorsione (0.001-0.01 consigliato)."""
        self.speed = speed
        """Velocita' dell'oscillazione."""
        self.scale = scale
        """Scala del pattern di distorsione."""

    def set_position(self, x: float, y: float):
        """Imposta la posizione della zona di distorsione."""
        self.x = x
        self.y = y

    def set_size(self, width: float, height: float):
        """Imposta le dimensioni della zona di distorsione."""
        self.width = width
        self.height = height

    def set_params(self, strength: float = None, speed: float = None,
                   scale: float = None):
        """Aggiorna i parametri di distorsione (solo quelli passati)."""
        if strength is not None:
            self.strength = strength
        if speed is not None:
            self.speed = speed
        if scale is not None:
            self.scale = scale


class HeatHazeManager:
    """Gestisce zone di heat haze persistenti."""

    MAX_HAZES = 4

    def __init__(self) -> None:
        self.hazes: list[HeatHaze] = []

    def add(self, x: float, y: float, width: float, height: float,
            strength: float = 0.003, speed: float = 3.0,
            scale: float = 20.0) -> HeatHaze:
        haze = HeatHaze(x, y, width, height, strength, speed, scale)
        self.hazes.append(haze)
        return haze

    def remove(self, haze: HeatHaze) -> None:
        try:
            self.hazes.remove(haze)
        except ValueError as e:
            cprint.warning(e)

    def get_count(self) -> int:
        """Ritorna il numero di heat haze attivi."""
        return len(self.hazes)

    def is_full(self) -> bool:
        """True se il buffer heat haze e' al massimo."""
        return len(self.hazes) >= self.MAX_HAZES

    def clear(self) -> None:
        self.hazes.clear()
