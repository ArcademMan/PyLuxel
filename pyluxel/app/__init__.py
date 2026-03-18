"""
pyluxel.app -- Bootstrap semplificato per applicazioni PyLuxel.

Uso minimo (decorator):
    from pyluxel import App

    app = App(1280, 720, "My Game")

    @app.on_draw
    def draw():
        app.draw_rect(100, 100, 50, 50, r=1, g=0, b=0)

    app.run()

Uso avanzato (subclass):
    class MyGame(App):
        def setup(self):
            self.player_x = 100

        def update(self, dt):
            self.player_x += 100 * dt

        def draw(self):
            self.draw_rect(self.player_x, 100, 32, 32, r=0, g=1, b=0)

    MyGame(1280, 720, "My Game").run()
"""

import os

import pygame
import moderngl

from pyluxel.core.resolution import Resolution
from pyluxel.core.renderer import Renderer
from pyluxel.core.sprite_batch import SpriteBatch
from pyluxel.core.texture_manager import TextureManager
from pyluxel.effects.lighting import Light, LightingSystem, FalloffMode
from pyluxel.core.post_fx import PostFX, HeatHaze, HeatHazeManager
from pyluxel.effects.transition import Transition, TransitionMode
from pyluxel.text.fonts import FontManager
from pyluxel.text.sdf_font import SDFFontCache
from pyluxel.input import Input
from pyluxel.audio import Sound
from pyluxel.debug import cprint
from pyluxel.debug.gpu_stats import GPUStats

from pyluxel.core.scene import SceneManager
from pyluxel.app.shapes import _ShapesMixin
from pyluxel.app.text import _TextMixin


class App(_ShapesMixin, _TextMixin):
    """Bootstrap completo per un'applicazione PyLuxel.

    Crea finestra, contesto OpenGL, renderer, sprite batch, lighting e
    texture manager in un singolo costruttore. Gestisce il game loop,
    gli eventi e il cleanup automatico.
    """

    def __init__(self, width: int = 1280, height: int = 720, title: str = "PyLuxel", *,
                 design_width: int | None = None, design_height: int | None = None,
                 fps: int = 60, vsync: bool = False, resizable: bool = False,
                 centered: bool = False,
                 clear_color: tuple = (0.05, 0.04, 0.07)):

        self._fps_cap = fps
        self._vsync = vsync
        self._is_fullscreen = False
        self._running = False

        # Design resolution defaults to window size
        dw = design_width if design_width is not None else width
        dh = design_height if design_height is not None else height

        # Debug
        self.show_fps: bool = False
        self.show_stats: bool = False

        # Post-processing
        self._ambient = 0.15
        self.fx = PostFX()

        # --- Pygame init ---
        pygame.init()
        try:
            from pygame._sdl2.controller import init as _ctrl_init
            _ctrl_init()
        except Exception as e:
            cprint.warning(e)

        if centered:
            os.environ['SDL_VIDEO_CENTERED'] = '1'

        flags = pygame.OPENGL | pygame.DOUBLEBUF
        if resizable:
            flags |= pygame.RESIZABLE

        if vsync:
            pygame.display.gl_set_attribute(pygame.GL_SWAP_CONTROL, 1)

        self._display = pygame.display.set_mode((width, height), flags, vsync=int(vsync))
        pygame.display.set_caption(title)

        # --- ModernGL context ---
        self.ctx: moderngl.Context = moderngl.create_context()

        # --- Resolution singleton ---
        R = Resolution()
        R.init(dw, dh)
        R.set_resolution(width, height)

        # --- Renderer (FBO pipeline) ---
        self.renderer: Renderer = Renderer(
            self.ctx, width, height,
            design_width=dw, design_height=dh,
            clear_color=clear_color,
        )

        # --- SpriteBatch ---
        self.batch: SpriteBatch = SpriteBatch(self.ctx, self.renderer.sprite_prog)

        # --- LightingSystem ---
        self.lighting: LightingSystem = LightingSystem(self.ctx, self.renderer.light_prog)
        self.lighting.set_renderer(self.renderer)

        # --- PAK auto-init (se data.pak esiste accanto all'exe, usalo) ---
        from pyluxel.core import paths as _paths
        pak_path = _paths.join(_paths.exe_dir(), "data.pak")
        if _paths.exists(pak_path):
            from pyluxel.core.pak import init_pak
            init_pak(pak_path)

        # --- TextureManager (no base path -- user loads what they want) ---
        self.textures: TextureManager = TextureManager(self.ctx, base_path=".")

        # --- 1x1 white texture ---
        self.white_tex: moderngl.Texture = self.textures.create_from_color(1, 1)

        # --- Text / SDF fonts ---
        FontManager.init("")
        self._sdf_cache = SDFFontCache(self.ctx, self.renderer.sdf_prog)

        # --- Input alias ---
        self.input = Input

        # --- Sound alias ---
        self.sound = Sound

        # --- Timing ---
        self._clock = pygame.time.Clock()
        self.dt: float = 0.0
        self.time: float = 0.0

        # --- Window state ---
        self._width = width
        self._height = height
        self._design_width = dw
        self._design_height = dh
        self._title = title
        self._resizable = resizable

        # --- SDF shapes (used by _ShapesMixin) ---
        self._sdf_ready = False
        self._shape_fill_ready = False

        # --- Persistent lights ---
        self._lights: list[Light] = []
        self.enable_shadows: bool = False
        """Se True, il shadow casters pass viene eseguito sempre,
        anche senza luci persistenti con cast_shadows. Utile quando
        le luci shadow-casting vengono aggiunte in draw_lights()."""

        # --- Scene manager ---
        self.scenes: SceneManager = SceneManager(self)

        # --- Camera ---
        self._camera = None

        # --- Networking ---
        self._net_active = False

        # --- Decorator callbacks ---
        self._update_cb = None
        self._draw_cb = None
        self._draw_lights_cb = None
        self._draw_overlay_cb = None
        self._event_cb = None
        self._resize_cb = None
        self._shadow_casters_cb = None

    def ShowFPS(self, val=True):
        if not isinstance(val, bool):
            val = True
        self.show_fps = val

    def ShowStats(self, val=True):
        if not isinstance(val, bool):
            val = True
        self.show_stats = val

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def width(self) -> int:
        """Larghezza finestra corrente."""
        return self._width

    @property
    def height(self) -> int:
        """Altezza finestra corrente."""
        return self._height

    @property
    def current_fps(self) -> float:
        """FPS corrente dal clock."""
        return self._clock.get_fps()

    @property
    def is_fullscreen(self) -> bool:
        """True se la finestra è in modalità fullscreen."""
        return self._is_fullscreen

    @property
    def fps_cap(self) -> int:
        """FPS cap corrente."""
        return self._fps_cap

    @fps_cap.setter
    def fps_cap(self, value: int):
        """Imposta il FPS cap."""
        self._fps_cap = value

    def get_font(self, name: str = "body"):
        """Ritorna l'oggetto SDFFont per il nome dato."""
        return self._sdf_cache.get(name)

    @property
    def camera(self):
        """Camera attiva. Se impostata, il game loop la passa a begin_scene()."""
        return self._camera

    @camera.setter
    def camera(self, cam):
        self._camera = cam

    @property
    def mouse_x(self) -> float:
        """Posizione X del mouse in design space."""
        mx, _ = pygame.mouse.get_pos()
        return mx * self._design_width / self._width

    @property
    def mouse_y(self) -> float:
        """Posizione Y del mouse in design space."""
        _, my = pygame.mouse.get_pos()
        return my * self._design_height / self._height

    @property
    def mouse_world_x(self) -> float:
        """Posizione X del mouse in coordinate mondo (usa la camera se attiva)."""
        sx = self.mouse_x
        if self._camera is not None:
            wx, _ = self._camera.screen_to_world(sx, 0)
            return wx
        return sx

    @property
    def mouse_world_y(self) -> float:
        """Posizione Y del mouse in coordinate mondo (usa la camera se attiva)."""
        sy = self.mouse_y
        if self._camera is not None:
            _, wy = self._camera.screen_to_world(0, sy)
            return wy
        return sy

    # ------------------------------------------------------------------
    # SpriteBatch shortcuts
    # ------------------------------------------------------------------

    def begin(self, texture: moderngl.Texture | None = None):
        """Inizia un batch. Default: white_tex. Auto-flush se ce n'è uno pendente."""
        if self.batch._count > 0:
            self.batch.end()
        self.batch.begin(texture if texture is not None else self.white_tex)

    def _auto_begin(self, texture: moderngl.Texture | None):
        """Auto-begin con la texture data (o white_tex). Flush se texture cambia."""
        tex = texture if texture is not None else self.white_tex
        if self.batch._current_texture is not tex:
            if self.batch._count > 0:
                self.batch.end()
            self.batch.begin(tex)

    def draw_sprite(self, x: float, y: float, w: float, h: float,
                    texture: moderngl.Texture | None = None,
                    u0: float = 0.0, v0: float = 0.0,
                    u1: float = 1.0, v1: float = 1.0,
                    r: float = 1.0, g: float = 1.0,
                    b: float = 1.0, a: float = 1.0,
                    angle: float = 0.0):
        """Aggiunge uno sprite al batch. Auto-begin con texture data o white_tex."""
        self._auto_begin(texture)
        self.batch.draw(x, y, w, h, u0, v0, u1, v1, r, g, b, a, angle)

    def draw_rect(self, x: float, y: float, w: float, h: float,
                  r: float = 1.0, g: float = 1.0,
                  b: float = 1.0, a: float = 1.0,
                  angle: float = 0.0):
        """Rettangolo colorato. angle==0: batch veloce. angle!=0: GPU SDF."""
        if angle == 0.0:
            self._auto_begin(None)
            self.batch.draw(x, y, w, h, r=r, g=g, b=b, a=a)
        else:
            self._sdf_draw('rect', x + w * 0.5, y + h * 0.5, w, h,
                           angle, r, g, b, a)

    def end(self):
        """Conclude il batch e disegna."""
        self.batch.end()

    # ------------------------------------------------------------------
    # Persistent lights
    # ------------------------------------------------------------------

    def add_light(self, x: float, y: float, radius: float = 150.0,
                  color: tuple = (1.0, 1.0, 0.9), intensity: float = 1.0,
                  falloff: FalloffMode | int = FalloffMode.QUADRATIC,
                  is_spotlight: bool = False,
                  direction: float = 0.0, angle: float = 45.0,
                  flicker_speed: float = 0.0, flicker_amount: float = 0.0,
                  flicker_style: str = "smooth",
                  z: float = 70.0,
                  cast_shadows: bool = False,
                  shadow_softness: float = 0.02) -> Light:
        """Crea una luce persistente. Aggiorna .x, .y, ecc. per spostarla."""
        light = Light(x, y, radius, color, intensity,
                      falloff, is_spotlight, direction, angle,
                      flicker_speed=flicker_speed,
                      flicker_amount=flicker_amount,
                      flicker_style=flicker_style, z=z,
                      cast_shadows=cast_shadows,
                      shadow_softness=shadow_softness)
        self._lights.append(light)
        return light

    def add_shockwave(self, x: float, y: float, max_radius: float = 200.0,
                      thickness: float = 30.0, strength: float = 0.05):
        """Crea un effetto shockwave di distorsione."""
        return self.renderer.shockwaves.add(x, y, max_radius, thickness, strength)

    def remove_light(self, light: Light):
        """Rimuovi una luce persistente."""
        try:
            self._lights.remove(light)
        except ValueError as e:
            cprint.warning(e)

    def clear_lights(self):
        """Rimuovi tutte le luci persistenti."""
        self._lights.clear()

    def get_lights(self) -> list[Light]:
        """Ritorna la lista delle luci persistenti."""
        return list(self._lights)

    @property
    def light_count(self) -> int:
        """Numero di luci persistenti attive."""
        return len(self._lights)

    # ------------------------------------------------------------------
    # Heat haze
    # ------------------------------------------------------------------

    def add_heat_haze(self, x: float, y: float, width: float, height: float,
                      strength: float = 0.003, speed: float = 3.0,
                      scale: float = 20.0) -> HeatHaze:
        """Crea una zona di distorsione persistente (calore, vapore, portali).

        Args:
            x, y: posizione top-left in design space
            width, height: dimensioni della zona
            strength: intensita' distorsione (0.001-0.01)
            speed: velocita' oscillazione
            scale: scala pattern distorsione

        Returns:
            Oggetto HeatHaze (modificabile a runtime).
        """
        return self.renderer.heat_hazes.add(x, y, width, height,
                                            strength, speed, scale)

    def remove_heat_haze(self, haze: HeatHaze):
        """Rimuovi una zona di heat haze."""
        self.renderer.heat_hazes.remove(haze)

    def clear_heat_hazes(self):
        """Rimuovi tutte le zone di heat haze."""
        self.renderer.heat_hazes.clear()

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def start_transition(self, mode: int = TransitionMode.FADE,
                         duration: float = 1.0,
                         color: tuple = (0.0, 0.0, 0.0),
                         reverse: bool = False,
                         on_complete=None):
        """Avvia una transizione di scena.

        Args:
            mode: TransitionMode.FADE/DISSOLVE/WIPE_LEFT/WIPE_DOWN/DIAMOND
            duration: durata in secondi
            color: colore target (default nero)
            reverse: True per fade-in (da colore a scena)
            on_complete: callback chiamato al termine
        """
        if not hasattr(self, '_transition') or self._transition is None:
            self._transition = Transition(self.ctx)
        self._transition.start(mode, duration, color, reverse, on_complete)

    def stop_transition(self):
        """Ferma la transizione corrente."""
        if hasattr(self, '_transition') and self._transition is not None:
            self._transition.stop()

    @property
    def transition_active(self) -> bool:
        """True se una transizione e' in corso."""
        if hasattr(self, '_transition') and self._transition is not None:
            return self._transition.active
        return False

    @property
    def transition_done(self) -> bool:
        """True se la transizione ha raggiunto la fine."""
        if hasattr(self, '_transition') and self._transition is not None:
            return self._transition.done
        return False

    @property
    def transition_progress(self) -> float:
        """Progresso corrente della transizione (0.0 -> 1.0)."""
        if hasattr(self, '_transition') and self._transition is not None:
            return self._transition.progress
        return 0.0

    # ------------------------------------------------------------------
    # God rays convenience
    # ------------------------------------------------------------------

    def set_god_rays(self, intensity: float = 0.5, x: float = 0.5,
                     y: float = 0.0, decay: float = 0.96,
                     density: float = 0.5):
        """Configura i god rays in un'unica chiamata.

        Args:
            intensity: intensita' (0 = off, 0.3-0.8 consigliato)
            x: posizione X sorgente (UV 0-1, 0.5 = centro)
            y: posizione Y sorgente (UV 0-1, 0.0 = top)
            decay: decadimento per sample (0.9-0.99)
            density: densita' raggi (0.3-1.0)
        """
        self.fx.god_rays = intensity
        self.fx.god_rays_x = x
        self.fx.god_rays_y = y
        self.fx.god_rays_decay = decay
        self.fx.god_rays_density = density

    # ------------------------------------------------------------------
    # Decorator registration
    # ------------------------------------------------------------------

    def on_update(self, fn):
        """Registra callback per update(dt)."""
        self._update_cb = fn
        return fn

    def on_draw(self, fn):
        """Registra callback per draw()."""
        self._draw_cb = fn
        return fn

    def on_draw_lights(self, fn):
        """Registra callback per draw_lights()."""
        self._draw_lights_cb = fn
        return fn

    def on_draw_overlay(self, fn):
        """Registra callback per draw_overlay()."""
        self._draw_overlay_cb = fn
        return fn

    def on_event(self, fn):
        """Registra callback per on_event(event)."""
        self._event_cb = fn
        return fn

    def on_resize(self, fn):
        """Registra callback per on_resize(width, height)."""
        self._resize_cb = fn
        return fn

    def on_shadow_casters(self, fn):
        """Registra callback per shadow_casters(). Disegna occluder per ombre."""
        self._shadow_casters_cb = fn
        return fn

    # ------------------------------------------------------------------
    # User-overridable hooks (subclass pattern)
    # ------------------------------------------------------------------

    def setup(self):
        """Chiamato una volta prima del game loop. Override in subclass."""
        pass

    def update(self, dt: float):
        """Logica di gioco. Override in subclass o usa @app.on_update."""
        if self._update_cb:
            self._update_cb(dt)

    def draw(self):
        """Rendering scena (scene FBO attivo). Override o @app.on_draw."""
        if self._draw_cb:
            self._draw_cb()

    def draw_lights(self):
        """Aggiunta luci (light FBO attivo). Override o @app.on_draw_lights."""
        if self._draw_lights_cb:
            self._draw_lights_cb()

    def shadow_casters(self):
        """Disegna occluder per ombre. Override o @app.on_shadow_casters."""
        if self._shadow_casters_cb:
            self._shadow_casters_cb()

    def draw_overlay(self):
        """HUD/UI sopra post-processing. Override o @app.on_draw_overlay."""
        if self._draw_overlay_cb:
            self._draw_overlay_cb()

    def handle_event(self, event: pygame.event.Event):
        """Evento pygame raw. Override o @app.on_event."""
        if self._event_cb:
            self._event_cb(event)

    def handle_resize(self, width: int, height: int):
        """Finestra ridimensionata. Override o @app.on_resize."""
        if self._resize_cb:
            self._resize_cb(width, height)

    # ------------------------------------------------------------------
    # Post-processing config
    # ------------------------------------------------------------------

    def set_post_process(self, *, ambient: float | None = None,
                         vignette: float | None = None,
                         bloom: float | None = None,
                         tone_mapping: bool | str | None = None,
                         exposure: float | None = None):
        """Configura i parametri di post-processing.

        Per accesso diretto a tutti gli effetti usa ``app.fx`` (PostFX).
        """
        if ambient is not None:
            self._ambient = ambient
        if vignette is not None:
            self.fx.vignette = vignette
        if bloom is not None:
            self.fx.bloom = bloom
        if tone_mapping is not None:
            if isinstance(tone_mapping, bool):
                self.fx.tone_mapping = "reinhard" if tone_mapping else "none"
            else:
                self.fx.tone_mapping = tone_mapping
        if exposure is not None:
            self.fx.exposure = exposure

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def quit(self):
        """Ferma il game loop."""
        self._running = False

    def toggle_fullscreen(self):
        """Alterna tra fullscreen e windowed."""
        self.set_fullscreen(not self._is_fullscreen)

    def set_window_title(self, title: str):
        """Cambia il titolo della finestra."""
        self._title = title
        pygame.display.set_caption(title)

    def get_window_title(self) -> str:
        """Ritorna il titolo corrente della finestra."""
        return self._title

    def get_design_resolution(self) -> tuple[int, int]:
        """Ritorna la design resolution (width, height)."""
        return self._design_width, self._design_height

    def get_window_resolution(self) -> tuple[int, int]:
        """Ritorna la risoluzione corrente della finestra."""
        return self._width, self._height

    def screenshot(self, path: str):
        """Salva uno screenshot come PNG."""
        data = self.renderer.screenshot()
        surf = pygame.image.frombytes(data, (self._width, self._height), "RGBA")
        # Il framebuffer OpenGL e' capovolto verticalmente
        surf = pygame.transform.flip(surf, False, True)
        pygame.image.save(surf, path)

    def set_fullscreen(self, fullscreen: bool):
        """Toggle fullscreen."""
        if fullscreen:
            self._display = pygame.display.set_mode(
                (0, 0), pygame.OPENGL | pygame.DOUBLEBUF | pygame.FULLSCREEN)
            info = pygame.display.get_window_size()
            self._width, self._height = info
            self._is_fullscreen = True
        else:
            flags = pygame.OPENGL | pygame.DOUBLEBUF
            if self._resizable:
                flags |= pygame.RESIZABLE
            self._display = pygame.display.set_mode(
                (self._design_width, self._design_height), flags)
            self._width = self._design_width
            self._height = self._design_height
            self._is_fullscreen = False

        self.renderer.resize(self._width, self._height)
        R = Resolution()
        R.set_resolution(self._width, self._height)

    def set_resolution(self, width: int, height: int):
        """Cambia la risoluzione della finestra (solo in modalità windowed)."""
        self._width = width
        self._height = height
        flags = pygame.OPENGL | pygame.DOUBLEBUF
        if self._resizable:
            flags |= pygame.RESIZABLE
        self._display = pygame.display.set_mode((width, height), flags,
                                                vsync=int(self._vsync))
        self.renderer.resize(width, height)
        R = Resolution()
        R.set_resolution(width, height)

    def set_vsync(self, enabled: bool):
        """Attiva/disattiva VSync a runtime. Ricrea il display."""
        self._vsync = enabled
        if enabled:
            pygame.display.gl_set_attribute(pygame.GL_SWAP_CONTROL, 1)
        else:
            pygame.display.gl_set_attribute(pygame.GL_SWAP_CONTROL, 0)
        flags = pygame.OPENGL | pygame.DOUBLEBUF
        if self._is_fullscreen:
            flags |= pygame.FULLSCREEN
        elif self._resizable:
            flags |= pygame.RESIZABLE
        self._display = pygame.display.set_mode(
            (self._width, self._height), flags, vsync=int(enabled))

    # ------------------------------------------------------------------
    # Game loop
    # ------------------------------------------------------------------

    def run(self):
        """Avvia il game loop principale."""
        self.setup()
        self._running = True

        while self._running:
            # --- Timing ---
            self.dt = self._clock.tick(self._fps_cap) / 1000.0
            self.dt = min(self.dt, 0.05)  # clamp a 20 FPS minimo
            self.time += self.dt
            GPUStats.reset_frame()

            # --- Events ---
            events = pygame.event.get()
            Input.update(events)

            for event in events:
                if event.type == pygame.QUIT:
                    self._running = False
                elif event.type == pygame.VIDEORESIZE:
                    self._width = event.w
                    self._height = event.h
                    self.renderer.resize(event.w, event.h)
                    R = Resolution()
                    R.set_resolution(event.w, event.h)
                    self.handle_resize(event.w, event.h)

                self.handle_event(event)

            # --- Network poll ---
            if self._net_active:
                try:
                    from pyluxel.net import Net
                    Net.poll(self.dt)
                except Exception as e:
                    cprint.warning(e)

            # --- Update ---
            self.update(self.dt)
            self.renderer.shockwaves.update(self.dt)

            # --- Render pipeline ---
            self.renderer.begin_scene(self._camera)
            self.draw()
            if self.batch._count > 0:
                self.batch.end()
            self._flush_text()

            # Shadow casters pass
            has_shadow_lights = self.enable_shadows or any(l.cast_shadows for l in self._lights)
            if has_shadow_lights:
                self.renderer.begin_shadow_casters()
                self.shadow_casters()
                if self.batch._count > 0:
                    self.batch.end()

            self.renderer.begin_lights()
            self.lighting.clear()
            for light in self._lights:
                self.lighting.lights.append(light)
            self.draw_lights()
            self.lighting.render(self.time)

            self.renderer.combine(ambient=self._ambient)
            self.renderer.post_process(self.fx)

            self.renderer.begin_screen_overlay()

            # Transition overlay (prima dell'HUD cosi' copre la scena)
            if hasattr(self, '_transition') and self._transition is not None:
                if self._transition.active:
                    self._transition.update(self.dt)
                    self._transition.render(
                        self.renderer.combine_texture,
                        self.renderer.screen_width,
                        self.renderer.screen_height)

            self.draw_overlay()
            if self.show_fps or self.show_stats:
                self._draw_debug_overlay()
            if self.batch._count > 0:
                self.batch.end()
            self._flush_text()

            pygame.display.flip()

        # --- Cleanup ---
        self._cleanup()
        pygame.quit()

    # ------------------------------------------------------------------
    # Debug overlay
    # ------------------------------------------------------------------

    def _draw_debug_overlay(self):
        """Disegna FPS e/o GPU stats nell'angolo in alto a sinistra."""
        y = 10
        clr = (0.8, 0.8, 0.8, 0.7)

        if self.show_fps or self.show_stats:
            self.draw_text(f"{self.current_fps:.0f} FPS", 10, y, size=18,
                           r=clr[0], g=clr[1], b=clr[2], a=clr[3])
            y += 20

        if self.show_stats:
            vram = GPUStats.calc_engine_vram(
                self.renderer, self.batch, self.textures,
                self.lighting, self._sdf_cache,
                self.white_tex)
            self.draw_text(
                f"VRAM: {vram:.1f} MB  |  Draw: {GPUStats.draw_calls}"
                f"  |  Sprites: {GPUStats.sprites}",
                10, y, size=16, r=clr[0], g=clr[1], b=clr[2], a=clr[3])
            y += 18

            total_mb, avail_mb = GPUStats.query_gpu_vram(self.ctx)
            if avail_mb >= 0:
                gpu_line = f"GPU: {avail_mb:.0f} MB free"
                if total_mb >= 0:
                    gpu_line += f" / {total_mb:.0f} MB"
                self.draw_text(gpu_line, 10, y, size=16,
                               r=clr[0], g=clr[1], b=clr[2], a=clr[3])

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _cleanup(self):
        """Rilascia tutte le risorse GPU."""
        # Network cleanup
        if self._net_active:
            try:
                from pyluxel.net import Net
                if Net.is_connected:
                    Net.disconnect()
            except Exception as e:
                cprint.warning("App cleanup - net:", e)

        self._cleanup_shapes()
        self._cleanup_text()

        try:
            Sound.release_all()
        except Exception as e:
            cprint.warning("App cleanup - sound:", e)

        try:
            self.white_tex.release()
        except Exception as e:
            cprint.warning("App cleanup - white_tex:", e)

        try:
            self.textures.release_all()
        except Exception as e:
            cprint.warning("App cleanup - textures:", e)

        try:
            self.lighting.release()
        except Exception as e:
            cprint.warning("App cleanup - lighting:", e)

        try:
            self.renderer.release()
        except Exception as e:
            cprint.warning("App cleanup - renderer:", e)
