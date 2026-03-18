from pyluxel.shaders import load_shader
from pyluxel.core.post_fx import PostFX, ShockwaveManager, HeatHazeManager
from pyluxel.debug import cprint
from pyluxel.debug.gpu_stats import GPUStats
import numpy as np
import moderngl
import pygame


MAX_SHADOW_ATLAS = 64


def _ortho_matrix(left, right, bottom, top, near=-1.0, far=1.0):
    """Matrice di proiezione ortografica."""
    m = np.zeros((4, 4), dtype="f4")
    m[0, 0] = 2.0 / (right - left)
    m[1, 1] = 2.0 / (top - bottom)
    m[2, 2] = -2.0 / (far - near)
    m[3, 0] = -(right + left) / (right - left)
    m[3, 1] = -(top + bottom) / (top - bottom)
    m[3, 2] = -(far + near) / (far - near)
    m[3, 3] = 1.0
    return m


BLOOM_MIP_LEVELS = 5


class Renderer:
    """Pipeline di rendering ModernGL con FBO HDR, lighting, bloom
    dual-kawase e post-processing avanzato."""

    def __init__(self, ctx: moderngl.Context, screen_width: int, screen_height: int,
                 design_width: int = 1280, design_height: int = 720,
                 clear_color: tuple = (15 / 255, 12 / 255, 18 / 255)):
        self.ctx = ctx
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.design_width = design_width
        self.design_height = design_height
        self.clear_color = clear_color

        # Camera offset (world → design space transform for shadow maps)
        self._cam_offset_x = 0.0
        self._cam_offset_y = 0.0
        self._cam_zoom = 1.0

        # Proiezione ortografica: design space, Y dall'alto verso il basso
        self.projection = _ortho_matrix(0, design_width, design_height, 0)

        # Shockwave manager
        self.shockwaves = ShockwaveManager()
        self.heat_hazes = HeatHazeManager()

        # --- Programmi shader ---
        self.sprite_prog = ctx.program(
            vertex_shader=load_shader("sprite.vert"),
            fragment_shader=load_shader("sprite.frag"),
        )
        self.screen_prog = ctx.program(
            vertex_shader=load_shader("screen.vert"),
            fragment_shader=load_shader("screen.frag"),
        )
        self.light_prog = ctx.program(
            vertex_shader=load_shader("light.vert"),
            fragment_shader=load_shader("light.frag"),
        )
        self.combine_prog = ctx.program(
            vertex_shader=load_shader("screen.vert"),
            fragment_shader=load_shader("combine.frag"),
        )
        self.post_prog = ctx.program(
            vertex_shader=load_shader("screen.vert"),
            fragment_shader=load_shader("post_process.frag"),
        )
        self.sdf_prog = ctx.program(
            vertex_shader=load_shader("sprite.vert"),
            fragment_shader=load_shader("sdf_text.frag"),
        )

        # Bloom shaders
        self.bloom_down_prog = ctx.program(
            vertex_shader=load_shader("screen.vert"),
            fragment_shader=load_shader("bloom_down.frag"),
        )
        self.bloom_up_prog = ctx.program(
            vertex_shader=load_shader("screen.vert"),
            fragment_shader=load_shader("bloom_up.frag"),
        )

        # Shadow map generation shader
        self.shadow_gen_prog = ctx.program(
            vertex_shader=load_shader("screen.vert"),
            fragment_shader=load_shader("shadow_1d.frag"),
        )

        # Set projection uniform
        self.sprite_prog["u_projection"].write(self.projection.tobytes())
        self.light_prog["u_projection"].write(self.projection.tobytes())
        self.sdf_prog["u_projection"].write(self.projection.tobytes())
        self.sdf_prog["u_smoothing"].value = 1.0

        # --- Fullscreen quad (clip space -1..1) ---
        quad_data = np.array([
            # pos        uv
            -1, -1,      0, 0,
             1, -1,      1, 0,
            -1,  1,      0, 1,
             1,  1,      1, 1,
        ], dtype="f4")
        self._quad_vbo = ctx.buffer(quad_data.tobytes())

        self._screen_vao = ctx.vertex_array(
            self.screen_prog,
            [(self._quad_vbo, "2f 2f", "in_position", "in_uv")],
        )
        self._combine_vao = ctx.vertex_array(
            self.combine_prog,
            [(self._quad_vbo, "2f 2f", "in_position", "in_uv")],
        )
        self._post_vao = ctx.vertex_array(
            self.post_prog,
            [(self._quad_vbo, "2f 2f", "in_position", "in_uv")],
        )
        self._bloom_down_vao = ctx.vertex_array(
            self.bloom_down_prog,
            [(self._quad_vbo, "2f 2f", "in_position", "in_uv")],
        )
        self._bloom_up_vao = ctx.vertex_array(
            self.bloom_up_prog,
            [(self._quad_vbo, "2f 2f", "in_position", "in_uv")],
        )
        self._shadow_gen_vao = ctx.vertex_array(
            self.shadow_gen_prog,
            [(self._quad_vbo, "2f 2f", "in_position", "in_uv")],
        )

        # --- FBOs ---
        self._create_fbos()

    def _create_fbos(self):
        """Crea i framebuffer HDR. Chiamare dopo cambio risoluzione."""
        dw, dh = self.design_width, self.design_height

        # Scene FBO (HDR - RGBA16F)
        self.scene_texture = self.ctx.texture((dw, dh), 4, dtype="f2")
        self.scene_texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.scene_fbo = self.ctx.framebuffer(
            color_attachments=[self.scene_texture])

        # Light FBO (HDR - RGBA16F)
        self.light_texture = self.ctx.texture((dw, dh), 4, dtype="f2")
        self.light_texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.light_fbo = self.ctx.framebuffer(
            color_attachments=[self.light_texture])

        # Combine FBO (HDR - RGBA16F)
        self.combine_texture = self.ctx.texture((dw, dh), 4, dtype="f2")
        self.combine_texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.combine_fbo = self.ctx.framebuffer(
            color_attachments=[self.combine_texture])

        # Normal map FBO (RGBA8 — tangent-space normals)
        self.normal_texture = self.ctx.texture((dw, dh), 4)
        self.normal_texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.normal_fbo = self.ctx.framebuffer(
            color_attachments=[self.normal_texture])
        self._normal_map_used = False

        # Occlusion FBO (RGBA8 — shadow casters)
        self.occlusion_texture = self.ctx.texture((dw, dh), 4)
        self.occlusion_texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.occlusion_fbo = self.ctx.framebuffer(
            color_attachments=[self.occlusion_texture])
        self._occlusion_used = False

        # Shadow map atlas (720 x MAX_SHADOW_ATLAS, R channel = distanza normalizzata)
        self.shadow_map_texture = self.ctx.texture(
            (720, MAX_SHADOW_ATLAS), 4)
        self.shadow_map_texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.shadow_map_fbo = self.ctx.framebuffer(
            color_attachments=[self.shadow_map_texture])

        # Bloom mip chain (1/2, 1/4, 1/8, 1/16, 1/32)
        self._bloom_textures: list[moderngl.Texture] = []
        self._bloom_fbos: list[moderngl.Framebuffer] = []
        for i in range(BLOOM_MIP_LEVELS):
            scale = 2 ** (i + 1)
            mip_w = max(1, dw // scale)
            mip_h = max(1, dh // scale)
            tex = self.ctx.texture((mip_w, mip_h), 4, dtype="f2")
            tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
            fbo = self.ctx.framebuffer(color_attachments=[tex])
            self._bloom_textures.append(tex)
            self._bloom_fbos.append(fbo)

    def get_design_resolution(self) -> tuple[int, int]:
        """Ritorna la design resolution corrente (width, height)."""
        return self.design_width, self.design_height

    def get_screen_resolution(self) -> tuple[int, int]:
        """Ritorna la risoluzione della finestra corrente (width, height)."""
        return self.screen_width, self.screen_height

    def set_clear_color(self, r: float, g: float, b: float):
        """Imposta il colore di clear della scena."""
        self.clear_color = (r, g, b)

    def get_clear_color(self) -> tuple:
        """Ritorna il colore di clear corrente."""
        return self.clear_color

    def screenshot(self) -> bytes:
        """Cattura il framebuffer corrente come bytes RGBA.

        Ritorna i dati raw del framebuffer. Per salvare come PNG:
            data = renderer.screenshot()
            import pygame
            surf = pygame.image.frombytes(data, (w, h), "RGBA")
            pygame.image.save(surf, "screenshot.png")
        """
        return self.ctx.screen.read(viewport=(0, 0, self.screen_width, self.screen_height))

    def resize(self, width: int, height: int):
        """Aggiorna la viewport per una nuova risoluzione della finestra."""
        self.screen_width = width
        self.screen_height = height

    def resize_design(self, design_width: int, design_height: int):
        """Cambia la risoluzione di design e ricrea FBO + proiezione."""
        self.design_width = design_width
        self.design_height = design_height
        self.projection = _ortho_matrix(0, design_width, design_height, 0)

        # Rilascia vecchi FBO
        for obj in (self.scene_fbo, self.scene_texture,
                    self.light_fbo, self.light_texture,
                    self.combine_fbo, self.combine_texture,
                    self.normal_fbo, self.normal_texture,
                    self.occlusion_fbo, self.occlusion_texture,
                    self.shadow_map_fbo, self.shadow_map_texture):
            try:
                obj.release()
            except Exception as e:
                cprint.warning("GPU release failed:", e)

        for tex in self._bloom_textures:
            try:
                tex.release()
            except Exception as e:
                cprint.warning("GPU release failed:", e)
        for fbo in self._bloom_fbos:
            try:
                fbo.release()
            except Exception as e:
                cprint.warning("GPU release failed:", e)

        self._create_fbos()

        # Aggiorna proiezione nei programmi shader
        proj_bytes = self.projection.tobytes()
        self.sprite_prog["u_projection"].write(proj_bytes)
        self.light_prog["u_projection"].write(proj_bytes)
        self.sdf_prog["u_projection"].write(proj_bytes)

    def apply_camera(self, camera):
        """Applica la camera alla proiezione. Tutte le draw call successive
        saranno in coordinate mondo con zoom automatico.

        Args:
            camera: Camera con posizione e zoom.
        """
        zoom = camera._zoom
        vw = self.design_width / zoom
        vh = self.design_height / zoom
        cx = camera.x + camera._shake_x
        cy = camera.y + camera._shake_y
        self._cam_offset_x = cx
        self._cam_offset_y = cy
        self._cam_zoom = zoom
        vp = _ortho_matrix(cx, cx + vw, cy + vh, cy)
        self._view_projection = vp
        vp_bytes = vp.tobytes()
        self.sprite_prog["u_projection"].write(vp_bytes)
        self.light_prog["u_projection"].write(vp_bytes)
        self.sdf_prog["u_projection"].write(vp_bytes)

    def reset_camera(self):
        """Ripristina la proiezione al design space (senza camera)."""
        self._view_projection = None
        self._cam_offset_x = 0.0
        self._cam_offset_y = 0.0
        self._cam_zoom = 1.0
        proj_bytes = self.projection.tobytes()
        self.sprite_prog["u_projection"].write(proj_bytes)
        self.light_prog["u_projection"].write(proj_bytes)
        self.sdf_prog["u_projection"].write(proj_bytes)

    def begin_scene(self, camera=None):
        """Inizia il rendering della scena.

        Args:
            camera: Camera opzionale. Se passata, tutte le draw call
                    usano coordinate mondo con zoom automatico.
        """
        self.scene_fbo.use()
        self.ctx.clear(*self.clear_color)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self._normal_map_used = False
        self._occlusion_used = False
        self._view_projection = None
        if camera is not None:
            self.apply_camera(camera)

    def begin_normal(self):
        """Inizia il rendering delle normal map.

        Disegnare le texture normal map degli sprite nello stesso ordine
        e posizione del begin_scene(). I pixel con alpha > 0 verranno
        illuminati con per-pixel normal mapping.

        Formato atteso: tangent-space normals (R=X, G=Y, B=Z).
        Il colore di default (128,128,255) = flat surface rivolta verso
        la camera.
        """
        self.normal_fbo.use()
        # Pulisci con alpha 0 = nessun normal map qui
        self.ctx.clear(0.5, 0.5, 1.0, 0.0)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self._normal_map_used = True

    def begin_shadow_casters(self):
        """Inizia il rendering degli occluder per le ombre.

        Disegnare sprite/forme bianche per indicare oggetti solidi che
        bloccano la luce. Il canale alpha determina l'occlusione:
            alpha = 1.0 -> blocca completamente
            alpha = 0.0 -> trasparente (nessuna ombra)

        Chiamare dopo begin_scene() e prima di begin_lights().
        """
        self.occlusion_fbo.use()
        self.ctx.clear(0.0, 0.0, 0.0, 0.0)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self._occlusion_used = True

    def _generate_shadow_map(self, light_x: float, light_y: float,
                             light_radius: float,
                             row: int = 0) -> moderngl.Texture:
        """Genera la shadow map 1D per una singola luce in una riga dell'atlas.

        Args:
            light_x, light_y: posizione della luce in design space
            light_radius: raggio della luce
            row: riga dell'atlas in cui scrivere (0..MAX_SHADOW_ATLAS-1)

        Returns:
            La texture shadow_map atlas.
        """
        self.shadow_map_fbo.use()
        self.ctx.viewport = (0, row, 720, 1)
        self.ctx.disable(moderngl.BLEND)

        self.occlusion_texture.use(0)
        self.shadow_gen_prog["u_occlusion_map"].value = 0
        self.shadow_gen_prog["u_light_center"].value = (light_x, light_y)
        self.shadow_gen_prog["u_resolution"].value = (
            float(self.design_width), float(self.design_height))
        self.shadow_gen_prog["u_max_distance"].value = light_radius

        self._shadow_gen_vao.render(moderngl.TRIANGLE_STRIP)
        GPUStats.record_draw()

        return self.shadow_map_texture

    def begin_lights(self):
        """Inizia il rendering delle luci."""
        self.light_fbo.use()
        self.ctx.clear(0.0, 0.0, 0.0, 0.0)
        self.ctx.enable(moderngl.BLEND)
        # Additive blending per le luci
        self.ctx.blend_func = moderngl.ONE, moderngl.ONE

        # Passa normal map al light shader (se usata)
        if self._normal_map_used:
            self.normal_texture.use(0)
            self.light_prog["u_normal_map"].value = 0
            self.light_prog["u_normal_enabled"].value = 1.0
            self.light_prog["u_resolution"].value = (
                float(self.design_width), float(self.design_height))
        else:
            self.light_prog["u_normal_enabled"].value = 0.0

        # Inizializza shadow a disabilitato
        self.light_prog["u_shadow_enabled"].value = 0.0

    def combine(self, ambient: float = 0.15, max_exposure: float = 1.5):
        """Combina scena e lightmap.

        Args:
            ambient: luce ambientale minima (0.0 = buio totale)
            max_exposure: valore massimo di luce (>1.0 per overexposure/glow)
        """
        self.combine_fbo.use()
        self.ctx.disable(moderngl.BLEND)

        self.scene_texture.use(0)
        self.light_texture.use(1)
        self.combine_prog["u_scene"].value = 0
        self.combine_prog["u_lightmap"].value = 1
        self.combine_prog["u_ambient"].value = ambient
        self.combine_prog["u_max_exposure"].value = max_exposure
        self._combine_vao.render(moderngl.TRIANGLE_STRIP)
        GPUStats.record_draw()

    def post_process(self, vignette: float | PostFX = 2.0, bloom: float = 0.5,
                     tone_mapping: bool = True):
        """Applica post-processing e disegna a schermo.

        Accetta la vecchia firma (vignette, bloom, tone_mapping) per
        backward compatibility, oppure un oggetto PostFX come primo argomento.

        Args:
            vignette: float per la vecchia API, oppure PostFX per la nuova
            bloom: intensita' bloom (solo vecchia API)
            tone_mapping: abilita tone mapping (solo vecchia API)
        """
        if isinstance(vignette, PostFX):
            fx = vignette
        else:
            fx = PostFX(
                vignette=vignette,
                bloom=bloom,
                tone_mapping="reinhard" if tone_mapping else "none",
                exposure=1.0,
            )
        self._render_post_process(fx)

    # ------------------------------------------------------------------
    # Bloom dual-kawase
    # ------------------------------------------------------------------

    def _render_bloom(self, source_tex: moderngl.Texture,
                      threshold: float = 0.8) -> moderngl.Texture | None:
        """Esegue il bloom dual-kawase e ritorna la texture del bloom.

        Returns:
            La texture bloom (mip[0]) oppure None se il bloom e' disattivato.
        """
        self.ctx.disable(moderngl.BLEND)

        # --- Downsample chain ---
        prev_tex = source_tex
        for i in range(BLOOM_MIP_LEVELS):
            self._bloom_fbos[i].use()
            prev_tex.use(0)

            self.bloom_down_prog["u_texture"].value = 0
            self.bloom_down_prog["u_resolution"].value = (
                float(prev_tex.width), float(prev_tex.height))
            # Threshold solo al primo passo
            self.bloom_down_prog["u_threshold"].value = threshold if i == 0 else 0.0

            self._bloom_down_vao.render(moderngl.TRIANGLE_STRIP)
            GPUStats.record_draw()

            prev_tex = self._bloom_textures[i]

        # --- Upsample chain ---
        for i in range(BLOOM_MIP_LEVELS - 1, 0, -1):
            # Render mip[i] upsampled into mip[i-1] (additive)
            self._bloom_fbos[i - 1].use()
            self._bloom_textures[i].use(0)
            self.ctx.enable(moderngl.BLEND)
            self.ctx.blend_func = moderngl.ONE, moderngl.ONE

            self.bloom_up_prog["u_texture"].value = 0
            self.bloom_up_prog["u_resolution"].value = (
                float(self._bloom_textures[i - 1].width),
                float(self._bloom_textures[i - 1].height))

            self._bloom_up_vao.render(moderngl.TRIANGLE_STRIP)
            GPUStats.record_draw()

        self.ctx.disable(moderngl.BLEND)
        return self._bloom_textures[0]

    # ------------------------------------------------------------------
    # Post-processing finale
    # ------------------------------------------------------------------

    def _render_post_process(self, fx: PostFX):
        """Rendering interno: applica tutti gli effetti e scrive a schermo."""
        # Bloom pass
        bloom_tex = None
        if fx.bloom > 0.0:
            bloom_tex = self._render_bloom(self.combine_texture)

        # Final pass to screen
        self.ctx.screen.use()
        self.ctx.viewport = (0, 0, self.screen_width, self.screen_height)
        self.ctx.disable(moderngl.BLEND)

        # Filtering: NEAREST per pixel art, LINEAR per smooth scaling
        _filt = moderngl.NEAREST if fx.pixel_perfect else moderngl.LINEAR
        self.combine_texture.filter = (_filt, _filt)

        # Bind textures
        self.combine_texture.use(0)
        self.post_prog["u_texture"].value = 0

        if bloom_tex is not None:
            bloom_tex.use(1)
            self.post_prog["u_bloom_texture"].value = 1

        if fx.color_grading_lut is not None:
            fx.color_grading_lut.use(2)
            self.post_prog["u_lut"].value = 2

        # Basic effects
        self.post_prog["u_vignette_strength"].value = fx.vignette
        self.post_prog["u_bloom_intensity"].value = fx.bloom
        self.post_prog["u_exposure"].value = fx.exposure

        # Tone mapping mode
        if fx.tone_mapping == "aces":
            self.post_prog["u_tone_mapping"].value = 2.0
        elif fx.tone_mapping == "reinhard":
            self.post_prog["u_tone_mapping"].value = 1.0
        else:
            self.post_prog["u_tone_mapping"].value = 0.0

        self.post_prog["u_resolution"].value = (
            float(self.design_width), float(self.design_height))

        # Toggleable effects
        self.post_prog["u_chromatic_aberration"].value = fx.chromatic_aberration
        self.post_prog["u_film_grain"].value = fx.film_grain
        self.post_prog["u_crt_enabled"].value = 1.0 if fx.crt else 0.0
        self.post_prog["u_crt_curvature"].value = fx.crt_curvature
        self.post_prog["u_crt_scanline"].value = fx.crt_scanline
        self.post_prog["u_lut_enabled"].value = 1.0 if fx.color_grading_lut is not None else 0.0
        self.post_prog["u_time"].value = pygame.time.get_ticks() / 1000.0

        # God rays
        self.post_prog["u_god_rays"].value = fx.god_rays
        if fx.god_rays > 0.0:
            self.post_prog["u_god_rays_source"].value = (fx.god_rays_x, fx.god_rays_y)
            self.post_prog["u_god_rays_decay"].value = fx.god_rays_decay
            self.post_prog["u_god_rays_density"].value = fx.god_rays_density

        # Shockwaves
        num_sw = min(len(self.shockwaves.shockwaves), ShockwaveManager.MAX_SHOCKWAVES)
        self.post_prog["u_num_shockwaves"].value = num_sw
        if num_sw > 0:
            centers = np.zeros(ShockwaveManager.MAX_SHOCKWAVES * 2, dtype="f4")
            params = np.zeros(ShockwaveManager.MAX_SHOCKWAVES * 4, dtype="f4")
            for i, sw in enumerate(self.shockwaves.shockwaves[:num_sw]):
                centers[i * 2] = sw.x
                centers[i * 2 + 1] = sw.y
                params[i * 4] = sw.radius
                params[i * 4 + 1] = sw.thickness
                params[i * 4 + 2] = sw.strength
            self.post_prog["u_shockwave_centers"].write(centers.tobytes())
            self.post_prog["u_shockwave_params"].write(params.tobytes())

        # Heat hazes
        num_haze = min(len(self.heat_hazes.hazes), HeatHazeManager.MAX_HAZES)
        self.post_prog["u_num_hazes"].value = num_haze
        if num_haze > 0:
            rects = np.zeros(HeatHazeManager.MAX_HAZES * 4, dtype="f4")
            hparams = np.zeros(HeatHazeManager.MAX_HAZES * 4, dtype="f4")
            for i, hz in enumerate(self.heat_hazes.hazes[:num_haze]):
                rects[i * 4] = hz.x
                rects[i * 4 + 1] = hz.y
                rects[i * 4 + 2] = hz.width
                rects[i * 4 + 3] = hz.height
                hparams[i * 4] = hz.strength
                hparams[i * 4 + 1] = hz.speed
                hparams[i * 4 + 2] = hz.scale
            self.post_prog["u_haze_rects"].write(rects.tobytes())
            self.post_prog["u_haze_params"].write(hparams.tobytes())

        self._post_vao.render(moderngl.TRIANGLE_STRIP)
        GPUStats.record_draw()

    def begin_screen_overlay(self):
        """Inizia a disegnare direttamente sullo schermo (per HUD/testo post-lighting)."""
        self.ctx.screen.use()
        self.ctx.viewport = (0, 0, self.screen_width, self.screen_height)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

        self.reset_camera()

    def blit_to_screen(self, texture: moderngl.Texture):
        """Disegna una texture direttamente a schermo (senza post-processing)."""
        self.ctx.screen.use()
        self.ctx.viewport = (0, 0, self.screen_width, self.screen_height)
        self.ctx.disable(moderngl.BLEND)

        texture.use(0)
        self.screen_prog["u_texture"].value = 0
        self._screen_vao.render(moderngl.TRIANGLE_STRIP)
        GPUStats.record_draw()

    def blit_overlay(self, texture: moderngl.Texture):
        """Disegna una texture overlay con alpha blending (per HUD)."""
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

        texture.use(0)
        self.screen_prog["u_texture"].value = 0
        self._screen_vao.render(moderngl.TRIANGLE_STRIP)
        GPUStats.record_draw()

    def release(self):
        """Rilascia tutte le risorse GPU (FBO, texture, shader, VAO, VBO)."""
        for obj in (
            self.scene_fbo, self.scene_texture,
            self.light_fbo, self.light_texture,
            self.combine_fbo, self.combine_texture,
            self.normal_fbo, self.normal_texture,
            self.occlusion_fbo, self.occlusion_texture,
            self.shadow_map_fbo, self.shadow_map_texture,
            self._screen_vao, self._combine_vao, self._post_vao,
            self._bloom_down_vao, self._bloom_up_vao,
            self._shadow_gen_vao,
            self._quad_vbo,
            self.sprite_prog, self.screen_prog, self.light_prog,
            self.combine_prog, self.post_prog, self.sdf_prog,
            self.bloom_down_prog, self.bloom_up_prog,
            self.shadow_gen_prog,
        ):
            try:
                obj.release()
            except Exception as e:
                cprint.warning("GPU release failed:", e)

        for tex in self._bloom_textures:
            try:
                tex.release()
            except Exception as e:
                cprint.warning("GPU release failed:", e)
        for fbo in self._bloom_fbos:
            try:
                fbo.release()
            except Exception as e:
                cprint.warning("GPU release failed:", e)
