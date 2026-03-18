from pyluxel.debug import cprint
from enum import IntEnum
import math
import random
import numpy as np
import moderngl


MAX_LIGHTS = 256
MAX_SHADOW_LIGHTS = 64


class FalloffMode(IntEnum):
    """Modalita' di attenuazione della luce."""
    LINEAR = 0
    QUADRATIC = 1
    CUBIC = 2


class Light:
    """Una luce puntuale 2D o spotlight con flicker opzionale."""

    __slots__ = ('x', 'y', 'z', 'radius', 'inner_radius', 'color', 'intensity',
                 'falloff', 'is_spotlight', 'direction', 'angle', 'inner_angle',
                 'cone_base',
                 'flicker_speed', 'flicker_amount', 'flicker_style',
                 '_base_intensity', '_flicker_phase',
                 'cast_shadows', 'shadow_softness')

    def __init__(self, x: float, y: float, radius: float = 150.0,
                 color: tuple = (1.0, 1.0, 0.9), intensity: float = 1.0,
                 falloff: FalloffMode | int = FalloffMode.QUADRATIC,
                 is_spotlight: bool = False,
                 direction: float = 0.0, angle: float = 45.0,
                 inner_angle: float = 0.0,
                 cone_base: float = 0.0,
                 flicker_speed: float = 0.0, flicker_amount: float = 0.0,
                 flicker_style: str = "smooth",
                 z: float = 70.0,
                 inner_radius: float = 0.0,
                 cast_shadows: bool = False,
                 shadow_softness: float = 0.02):
        self.x = x
        self.y = y
        self.z = z
        """Altezza della luce sopra la superficie (per normal mapping). Default 70."""
        self.radius = max(1.0, radius)
        self.inner_radius = max(0.0, inner_radius)
        """Raggio interno: la luce inizia da questa distanza (0=dal centro). Default 0."""
        self.color = color
        self.intensity = max(0.0, intensity)
        self.falloff = FalloffMode(falloff)
        self.is_spotlight = is_spotlight
        self.direction = direction  # gradi (0=destra, 90=giu')
        self.angle = angle          # ampiezza cono in gradi
        self.inner_angle = max(0.0, inner_angle)
        """Angolo interno spotlight: piena intensita' dentro, sfumatura verso angle. Default 0."""
        self.cone_base = max(0.0, min(cone_base, 90.0))
        """Base del cono spotlight (0=punta, 90=rettangolo). Tronca il cono alla sorgente."""

        # Flicker
        self.flicker_speed = flicker_speed
        """Velocita' del flicker (0=off). Consigliato: 5-15 per torce, 20-40 per neon."""
        self.flicker_amount = flicker_amount
        """Ampiezza del flicker (0-1). 0.2=sottile, 0.5=evidente, 0.8=drammatico."""
        self.flicker_style = flicker_style
        """Stile: 'smooth' (sinusoidale), 'harsh' (neon rotto), 'candle' (organico)."""
        self._base_intensity = intensity
        self._flicker_phase = random.random() * 100.0

        # Shadows
        self.cast_shadows = cast_shadows
        """Se True, questa luce proietta ombre dagli occluder."""
        self.shadow_softness = shadow_softness
        """Morbidezza del bordo dell'ombra (0.01=duro, 0.1=morbido). Default 0.02."""

    def set_position(self, x: float, y: float):
        """Imposta la posizione della luce."""
        self.x = x
        self.y = y

    def set_color(self, r: float, g: float, b: float):
        """Imposta il colore della luce (RGB 0-1)."""
        self.color = (r, g, b)

    def set_intensity(self, intensity: float):
        """Imposta l'intensita' base della luce."""
        self.intensity = max(0.0, intensity)

    def set_radius(self, radius: float):
        """Imposta il raggio della luce."""
        self.radius = max(1.0, radius)

    def set_falloff(self, mode: FalloffMode | int):
        """Imposta la curva di attenuazione (LINEAR, QUADRATIC, CUBIC)."""
        self.falloff = FalloffMode(mode)

    def set_inner_radius(self, inner_radius: float):
        """Imposta il raggio interno (la luce inizia da questa distanza)."""
        self.inner_radius = max(0.0, inner_radius)

    def set_spotlight(self, direction: float, angle: float, inner_angle: float = 0.0,
                      cone_base: float = 0.0):
        """Configura come spotlight con direzione e ampiezza cono.

        Args:
            direction: direzione in gradi (0=destra, 90=giu')
            angle: ampiezza cono esterno in gradi
            inner_angle: ampiezza cono interno in gradi (piena intensita'). Default 0.
            cone_base: tronca la punta del cono (0=punta, 90=rettangolo). Default 0.
        """
        self.is_spotlight = True
        self.direction = direction
        self.angle = angle
        self.inner_angle = max(0.0, inner_angle)
        self.cone_base = max(0.0, min(cone_base, 90.0))

    def set_inner_angle(self, inner_angle: float):
        """Imposta l'angolo interno dello spotlight (piena intensita')."""
        self.inner_angle = max(0.0, inner_angle)

    def set_direction(self, direction: float):
        """Imposta la direzione dello spotlight in gradi."""
        self.direction = direction

    def set_flicker(self, speed: float, amount: float,
                    style: str = "smooth"):
        """Configura il flicker della luce.

        Args:
            speed: velocita' (0=off, 8=torcia, 30=neon)
            amount: ampiezza (0-1)
            style: 'smooth', 'harsh', 'candle'
        """
        self.flicker_speed = speed
        self.flicker_amount = amount
        self.flicker_style = style

    def set_z(self, z: float):
        """Imposta l'altezza della luce per normal mapping."""
        self.z = z

    def set_shadow_casting(self, enabled: bool, softness: float = 0.02):
        """Abilita/disabilita le ombre per questa luce.

        Args:
            enabled: True per proiettare ombre
            softness: morbidezza bordo (0.01=duro, 0.1=morbido)
        """
        self.cast_shadows = enabled
        self.shadow_softness = softness

    def get_position(self) -> tuple[float, float]:
        """Ritorna la posizione (x, y) della luce."""
        return self.x, self.y

    def get_color(self) -> tuple:
        """Ritorna il colore RGB della luce."""
        return self.color

    def get_intensity(self) -> float:
        """Ritorna l'intensita' base della luce."""
        return self.intensity

    def get_radius(self) -> float:
        """Ritorna il raggio della luce."""
        return self.radius

    def query_point(self, px: float, py: float,
                    walls: list[tuple[float, float, float, float]] | None = None
                    ) -> float:
        """Calcola l'esposizione di un punto a questa luce (CPU-side).

        Replica la logica dello shader: distanza, falloff, cono spotlight,
        e (opzionalmente) occlusione da muri AABB.

        Args:
            px, py: posizione del punto da testare
            walls: lista opzionale di AABB (x, y, w, h) che bloccano la luce.
                   Se None, non viene effettuato il test di occlusione.

        Returns:
            Valore tra 0.0 (buio totale) e 1.0 (piena luce).
        """
        dx = px - self.x
        dy = py - self.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > self.radius:
            return 0.0

        # Inner radius: nessuna luce dentro inner_radius
        inner_ratio = self.inner_radius / self.radius if self.radius > 0 else 0.0
        dr = dist / self.radius
        if dr < inner_ratio:
            return 0.0

        # Remap da [inner_ratio, 1] a [0, 1]
        if inner_ratio < 1.0:
            remapped = (dr - inner_ratio) / (1.0 - inner_ratio)
        else:
            return 0.0

        # Falloff
        if self.falloff == FalloffMode.LINEAR:
            attenuation = 1.0 - remapped
        elif self.falloff == FalloffMode.CUBIC:
            attenuation = 1.0 - remapped * remapped * remapped
        else:  # QUADRATIC
            attenuation = 1.0 - remapped * remapped

        if attenuation <= 0.0:
            return 0.0

        # Spotlight cone
        cone_factor = 1.0
        if self.is_spotlight:
            cone_base = getattr(self, 'cone_base', 0.0)
            trunc = min(cone_base / 90.0, 1.0) if cone_base > 0 else 0.0

            if trunc > 0.001:
                # Trapezoid mode (cone_base > 0)
                dir_rad = math.radians(self.direction)
                dir_x = math.cos(dir_rad)
                dir_y = math.sin(dir_rad)
                frag_x = dx
                frag_y = -dy

                along = frag_x * dir_x + frag_y * dir_y
                perp_x = frag_x - dir_x * along
                perp_y = frag_y - dir_y * along
                perp = math.sqrt(perp_x * perp_x + perp_y * perp_y)

                along_n = along / self.radius if self.radius > 0 else 0.0
                perp_n = perp / self.radius if self.radius > 0 else 0.0

                half_rad = math.radians(self.angle * 0.5)
                tan_half = math.tan(half_rad) if half_rad < math.pi * 0.49 else 100.0
                max_perp = tan_half * (trunc + max(along_n, 0.0) * (1.0 - trunc))

                edge = max(max_perp * 0.08, 0.01)
                if perp_n >= max_perp + edge:
                    return 0.0
                elif perp_n <= max_perp - edge:
                    pass
                else:
                    t = (max_perp + edge - perp_n) / (2.0 * edge)
                    cone_factor = t * t * (3.0 - 2.0 * t)

                if along_n < -0.01:
                    return 0.0
                elif along_n < 0.02:
                    t = (along_n + 0.01) / 0.03
                    cone_factor *= t * t * (3.0 - 2.0 * t)
            else:
                # Standard cone mode
                frag_angle = math.atan2(-dy, dx)
                dir_rad = math.radians(self.direction)
                frag_len = math.sqrt(dx * dx + dy * dy)
                if frag_len < 0.001:
                    cos_angle = 1.0
                else:
                    cos_angle = (math.cos(frag_angle) * math.cos(dir_rad)
                                 + math.sin(frag_angle) * math.sin(dir_rad))
                cos_outer = math.cos(math.radians(self.angle * 0.5))
                cos_inner = math.cos(math.radians(self.inner_angle * 0.5))

                if self.inner_angle > 0.0 and cos_inner < 0.9999:
                    if cos_angle <= cos_outer:
                        return 0.0
                    elif cos_angle >= cos_inner:
                        cone_factor = 1.0
                    else:
                        t = (cos_angle - cos_outer) / (cos_inner - cos_outer)
                        cone_factor = t * t * (3.0 - 2.0 * t)
                else:
                    edge_softness = 0.05
                    lo = cos_outer - edge_softness
                    hi = cos_outer + edge_softness
                    if cos_angle <= lo:
                        return 0.0
                    elif cos_angle >= hi:
                        cone_factor = 1.0
                    else:
                        t = (cos_angle - lo) / (hi - lo)
                        cone_factor = t * t * (3.0 - 2.0 * t)

        # Occlusione da muri
        if walls:
            from pyluxel.physics.collision import ray_vs_aabb
            for wx, wy, ww, wh in walls:
                t = ray_vs_aabb(self.x, self.y, dx, dy, wx, wy, ww, wh)
                if t is not None and t < 0.99:
                    return 0.0

        return max(0.0, attenuation * cone_factor)

    def compute_intensity(self, time: float) -> float:
        """Calcola l'intensita' con flicker applicato."""
        if self.flicker_speed <= 0 or self.flicker_amount <= 0:
            return self.intensity
        flicker = self._compute_flicker_value(time)
        mod = 1.0 - self.flicker_amount * (1.0 - flicker)
        return self.intensity * max(mod, 0.0)

    def _compute_flicker_value(self, time: float) -> float:
        """Calcola il valore base del flicker (0..1)."""
        t = time * self.flicker_speed + self._flicker_phase
        style = self.flicker_style

        if style == "harsh":
            wave = math.sin(t * 3.7) + math.sin(t * 7.3) * 0.5
            return 1.0 if wave > -0.2 else 0.1
        elif style == "candle":
            flicker = (math.sin(t) * 0.4
                       + math.sin(t * 1.7) * 0.3
                       + math.sin(t * 2.9) * 0.2
                       + math.sin(t * 4.3) * 0.1)
            return flicker * 0.5 + 0.5
        else:
            return math.sin(t) * 0.5 + 0.5

    def compute_flicker(self, time: float):
        """Calcola intensita', colore e radius con flicker applicato.

        Ritorna (intensity, color, radius). Per stile 'candle', colore e
        radius variano leggermente per simulare una fiamma reale.
        """

        if self.flicker_speed <= 0 or self.flicker_amount <= 0:
            return self.intensity, self.color, self.radius

        t = time * self.flicker_speed + self._flicker_phase
        flicker = self._compute_flicker_value(time)
        mod = 1.0 - self.flicker_amount * (1.0 - flicker)
        intensity = self.intensity * max(mod, 0.0)

        color = self.color
        radius = self.radius

        if self.flicker_style == "candle":
            # Variazione colore: shift verso rosso quando l'intensità cala
            color_shift = (1.0 - flicker) * self.flicker_amount * 0.3
            cr = min(color[0] + color_shift * 0.1, 1.0)
            cg = max(color[1] - color_shift, 0.0)
            cb = max(color[2] - color_shift * 0.5, 0.0)
            color = (cr, cg, cb)

            # Variazione radius: oscillazione indipendente, leggera
            radius_wave = math.sin(t * 1.3 + 2.0) * 0.5 + 0.5
            radius = self.radius * (1.0 - self.flicker_amount * 0.08 * (1.0 - radius_wave))

        return intensity, color, radius


# Floats per vertex: position(2) + uv(2) + light_data(4) + extra(4) + light_world(4) + inner(3) = 19
_FLOATS_PER_VERTEX = 19
_FLOATS_PER_QUAD = _FLOATS_PER_VERTEX * 4


def _fill_light_quad(vd, offset: int, light: Light, intensity: float,
                     color: tuple = None, radius: float = None,
                     atlas_row: float = 0.0):
    """Scrive i 76 float di un quad luce nel buffer vertex data."""
    r = radius if radius is not None else light.radius
    x = light.x - r
    y = light.y - r
    s = r * 2
    cr, cg, cb = color if color is not None else light.color

    falloff_f = float(light.falloff)
    is_spot_f = 1.0 if light.is_spotlight else 0.0
    cos_half = float(np.cos(np.radians(light.angle * 0.5)))
    dir_rad = float(np.radians(light.direction))

    cx = light.x
    cy = light.y
    lz = light.z

    # Inner params
    inner_ratio = light.inner_radius / r if r > 0 else 0.0
    cos_inner_half = float(np.cos(np.radians(light.inner_angle * 0.5)))
    cone_base = getattr(light, 'cone_base', 0.0)
    trunc_ratio = min(cone_base / 90.0, 1.0) if cone_base > 0 else 0.0

    j = offset
    # bottom-left
    vd[j]     = x;     vd[j+1]  = y + s
    vd[j+2]   = 0.0;   vd[j+3]  = 0.0
    vd[j+4]   = cr;    vd[j+5]  = cg;  vd[j+6]  = cb;  vd[j+7]  = intensity
    vd[j+8]   = falloff_f; vd[j+9] = is_spot_f; vd[j+10] = cos_half; vd[j+11] = dir_rad
    vd[j+12]  = cx;    vd[j+13] = cy;   vd[j+14] = lz;  vd[j+15] = atlas_row
    vd[j+16]  = inner_ratio; vd[j+17] = cos_inner_half; vd[j+18] = trunc_ratio
    # bottom-right
    vd[j+19]  = x + s; vd[j+20] = y + s
    vd[j+21]  = 1.0;   vd[j+22] = 0.0
    vd[j+23]  = cr;    vd[j+24] = cg;  vd[j+25] = cb;  vd[j+26] = intensity
    vd[j+27]  = falloff_f; vd[j+28] = is_spot_f; vd[j+29] = cos_half; vd[j+30] = dir_rad
    vd[j+31]  = cx;    vd[j+32] = cy;   vd[j+33] = lz;  vd[j+34] = atlas_row
    vd[j+35]  = inner_ratio; vd[j+36] = cos_inner_half; vd[j+37] = trunc_ratio
    # top-right
    vd[j+38]  = x + s; vd[j+39] = y
    vd[j+40]  = 1.0;   vd[j+41] = 1.0
    vd[j+42]  = cr;    vd[j+43] = cg;  vd[j+44] = cb;  vd[j+45] = intensity
    vd[j+46]  = falloff_f; vd[j+47] = is_spot_f; vd[j+48] = cos_half; vd[j+49] = dir_rad
    vd[j+50]  = cx;    vd[j+51] = cy;   vd[j+52] = lz;  vd[j+53] = atlas_row
    vd[j+54]  = inner_ratio; vd[j+55] = cos_inner_half; vd[j+56] = trunc_ratio
    # top-left
    vd[j+57]  = x;     vd[j+58] = y
    vd[j+59]  = 0.0;   vd[j+60] = 1.0
    vd[j+61]  = cr;    vd[j+62] = cg;  vd[j+63] = cb;  vd[j+64] = intensity
    vd[j+65]  = falloff_f; vd[j+66] = is_spot_f; vd[j+67] = cos_half; vd[j+68] = dir_rad
    vd[j+69]  = cx;    vd[j+70] = cy;   vd[j+71] = lz;  vd[j+72] = atlas_row
    vd[j+73]  = inner_ratio; vd[j+74] = cos_inner_half; vd[j+75] = trunc_ratio


class LightingSystem:
    """Sistema di illuminazione 2D con luci puntuali/spotlight additive.

    Tutte le luci vengono batchate in un singolo draw call.
    Supporta falloff configurabile (lineare/quadratico/cubico), spotlight e ombre.
    """

    def __init__(self, ctx: moderngl.Context, light_prog: moderngl.Program):
        self.ctx = ctx
        self.prog = light_prog
        self.lights: list[Light] = []
        self._renderer = None

        # Vertex buffer
        self._vertex_data = np.zeros(MAX_LIGHTS * _FLOATS_PER_QUAD, dtype="f4")
        self._vbo = ctx.buffer(reserve=self._vertex_data.nbytes, dynamic=True)

        # Index buffer: 2 triangles per quad
        indices = []
        for i in range(MAX_LIGHTS):
            b = i * 4
            indices.extend([b, b + 1, b + 2, b + 2, b + 3, b])
        self._ibo = ctx.buffer(np.array(indices, dtype="i4").tobytes())

        self._vao = ctx.vertex_array(
            light_prog,
            [(self._vbo, "2f 2f 4f 4f 4f 3f",
              "in_position", "in_uv", "in_light_data", "in_extra",
              "in_light_world", "in_inner_params")],
            index_buffer=self._ibo,
        )

    def set_renderer(self, renderer):
        """Collega il renderer per la generazione delle shadow map.

        Chiamato automaticamente dalla classe App. Per uso manuale,
        chiamare prima di usare luci con cast_shadows=True.
        """
        self._renderer = renderer

    def clear(self):
        """Rimuovi tutte le luci."""
        self.lights.clear()

    def remove(self, light: Light) -> None:
        """Rimuovi una singola luce."""
        try:
            self.lights.remove(light)
        except ValueError as e:
            cprint.warning(e)

    def get_light_count(self) -> int:
        """Ritorna il numero di luci attive."""
        return len(self.lights)

    def is_full(self) -> bool:
        """True se il buffer luci e' al massimo."""
        return len(self.lights) >= MAX_LIGHTS

    def add(self, x: float, y: float, radius: float = 150.0,
            color: tuple = (1.0, 1.0, 0.9), intensity: float = 1.0,
            falloff: FalloffMode | int = FalloffMode.QUADRATIC,
            is_spotlight: bool = False,
            direction: float = 0.0, angle: float = 45.0,
            inner_angle: float = 0.0,
            cone_base: float = 0.0,
            flicker_speed: float = 0.0, flicker_amount: float = 0.0,
            flicker_style: str = "smooth",
            z: float = 70.0,
            inner_radius: float = 0.0,
            cast_shadows: bool = False,
            shadow_softness: float = 0.02) -> Light:
        """Aggiungi una luce.

        Inner parametri (opzionali):
            inner_radius: raggio interno, la luce inizia da questa distanza (0=dal centro)
            inner_angle: angolo interno spotlight, piena intensita' dentro (0=nessuno)

        Flicker parametri (opzionali):
            flicker_speed: velocita' oscillazione (0=off, 8=torcia, 30=neon)
            flicker_amount: ampiezza (0-1, 0.2=sottile, 0.5=evidente)
            flicker_style: 'smooth' (sinusoide), 'harsh' (neon), 'candle' (organico)

        Shadow parametri (opzionali):
            cast_shadows: True per proiettare ombre (max 64 luci)
            shadow_softness: morbidezza bordo ombra (0.01=duro, 0.1=morbido)
        """
        light = Light(x, y, radius, color, intensity,
                      falloff, is_spotlight, direction, angle, inner_angle,
                      cone_base,
                      flicker_speed, flicker_amount, flicker_style, z,
                      inner_radius, cast_shadows, shadow_softness)
        self.lights.append(light)
        return light

    def query_point(self, px: float, py: float,
                    walls: list[tuple[float, float, float, float]] | None = None
                    ) -> float:
        """Calcola l'esposizione totale di un punto da tutte le luci.

        Utile per gameplay (stealth, visibilita', danno da luce).
        Ritorna il massimo tra tutte le luci (non la somma).

        Args:
            px, py: punto da testare
            walls: AABB opzionali che bloccano la luce

        Returns:
            Valore tra 0.0 e 1.0.
        """
        best = 0.0
        for light in self.lights:
            exp = light.query_point(px, py, walls)
            if exp > best:
                best = exp
                if best >= 1.0:
                    return 1.0
        return best

    def get_lights_affecting(self, px: float, py: float,
                             walls: list[tuple[float, float, float, float]] | None = None
                             ) -> list[tuple[Light, float]]:
        """Ritorna tutte le luci che illuminano il punto, con la loro esposizione.

        Returns:
            Lista di (light, exposure) per ogni luce con exposure > 0.
        """
        result = []
        for light in self.lights:
            exp = light.query_point(px, py, walls)
            if exp > 0.0:
                result.append((light, exp))
        return result

    def render(self, time: float = 0.0):
        """Disegna tutte le luci.

        Le luci con cast_shadows=True vengono renderizzate in batch con
        shadow map atlas. Le altre vengono batchate senza shadow.

        Args:
            time: tempo corrente in secondi (per flicker). Se 0, flicker disabilitato.
        """
        count = min(len(self.lights), MAX_LIGHTS)
        if count == 0:
            return

        shadow_lights = []
        non_shadow_lights = []

        for light in self.lights[:count]:
            if light.cast_shadows:
                shadow_lights.append(light)
            else:
                non_shadow_lights.append(light)

        if len(shadow_lights) > MAX_SHADOW_LIGHTS:
            cprint.warning(f"Troppe shadow lights ({len(shadow_lights)}), "
                           f"limite a {MAX_SHADOW_LIGHTS}")
            non_shadow_lights.extend(shadow_lights[MAX_SHADOW_LIGHTS:])
            shadow_lights = shadow_lights[:MAX_SHADOW_LIGHTS]

        # Pass 1: shadow lights (batch con atlas)
        if shadow_lights and self._renderer and self._renderer._occlusion_used:
            self._render_shadow_batch(shadow_lights, time)

        # Pass 2: non-shadow lights (batch)
        if non_shadow_lights:
            self._render_batched(non_shadow_lights, time)

    def _render_shadow_batch(self, shadow_lights: list[Light], time: float):
        """Genera shadow map atlas e renderizza tutte le shadow lights in batch."""
        from pyluxel.core.renderer import MAX_SHADOW_ATLAS

        cam_x = self._renderer._cam_offset_x
        cam_y = self._renderer._cam_offset_y
        cam_z = self._renderer._cam_zoom

        # --- Fase 1: genera tutte le shadow map nell'atlas ---
        self._renderer.shadow_map_fbo.use()
        self.ctx.clear(1.0, 0.0, 0.0, 1.0)  # dist=1.0 = nessun occluder

        for row, light in enumerate(shadow_lights):
            design_lx = (light.x - cam_x) * cam_z
            design_ly = (light.y - cam_y) * cam_z
            design_radius = light.radius * cam_z
            self._renderer._generate_shadow_map(
                design_lx, design_ly, design_radius, row=row)

        # --- Fase 2: batch render con atlas ---
        self._renderer.light_fbo.use()
        dw = self._renderer.design_width
        dh = self._renderer.design_height
        self.ctx.viewport = (0, 0, dw, dh)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.ONE, moderngl.ONE

        # Bind shadow atlas
        self._renderer.shadow_map_texture.use(1)
        self.prog["u_shadow_map"].value = 1
        self.prog["u_shadow_enabled"].value = 1.0
        self.prog["u_shadow_softness"].value = shadow_lights[0].shadow_softness
        self.prog["u_atlas_height"].value = float(MAX_SHADOW_ATLAS)

        # Scrivi vertex data per tutte le shadow lights
        n = len(shadow_lights)
        vd = self._vertex_data
        for i, light in enumerate(shadow_lights):
            intensity, color, radius = light.compute_flicker(time)
            _fill_light_quad(vd, i * _FLOATS_PER_QUAD, light,
                             intensity, color, radius, atlas_row=float(i))

        self._vbo.write(vd[:n * _FLOATS_PER_QUAD].tobytes())
        self._vao.render(moderngl.TRIANGLES, vertices=n * 6)

        from pyluxel.debug.gpu_stats import GPUStats
        GPUStats.record_draw()

        # Disabilita shadow per le prossime luci
        self.prog["u_shadow_enabled"].value = 0.0

    def _render_batched(self, lights: list[Light], time: float):
        """Renderizza luci in un singolo draw call batchato."""
        count = len(lights)
        if count == 0:
            return

        self.prog["u_shadow_enabled"].value = 0.0

        vd = self._vertex_data
        for i in range(count):
            intensity, color, radius = lights[i].compute_flicker(time)
            _fill_light_quad(vd, i * _FLOATS_PER_QUAD, lights[i], intensity, color, radius)

        self._vbo.write(vd[:count * _FLOATS_PER_QUAD].tobytes())
        self._vao.render(moderngl.TRIANGLES, vertices=count * 6)

        from pyluxel.debug.gpu_stats import GPUStats
        GPUStats.record_draw()

    def release(self):
        """Free GPU resources."""
        for obj in (self._vao, self._vbo, self._ibo):
            try:
                obj.release()
            except Exception as e:
                cprint.warning("GPU release failed:", e)
