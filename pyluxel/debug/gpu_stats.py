"""GPU Stats -- tracking draw call, sprite count e VRAM usage."""

import ctypes
import sys

from pyluxel.debug import cprint


def _tex_bytes(tex) -> int:
    """Calcola VRAM di una texture moderngl."""
    return tex.width * tex.height * tex.components


class GPUStats:
    """Singleton statico per tracking GPU stats per frame."""

    # --- Per-frame counters (reset ogni frame) ---
    draw_calls: int = 0
    sprites: int = 0

    # --- VRAM cache (ricalcolata ogni N frame) ---
    _vram_engine_mb: float = 0.0
    _gpu_total_mb: float = -1.0
    _gpu_available_mb: float = -1.0
    _frame_counter: int = 0
    _gpu_queried: bool = False

    # --- GL extension enums ---
    _GL_GPU_MEM_INFO_TOTAL_AVAILABLE_MEM_NVX = 0x9048
    _GL_GPU_MEM_INFO_CURRENT_AVAILABLE_MEM_NVX = 0x9049
    _GL_TEXTURE_FREE_MEMORY_ATI = 0x87FC

    @classmethod
    def reset_frame(cls):
        """Resetta i contatori per-frame. Chiamare a inizio frame."""
        cls.draw_calls = 0
        cls.sprites = 0

    @classmethod
    def record_draw(cls, sprite_count: int = 0):
        """Registra un draw call. sprite_count = quanti sprite/char in questo draw."""
        cls.draw_calls += 1
        cls.sprites += sprite_count

    # ------------------------------------------------------------------
    # VRAM engine
    # ------------------------------------------------------------------

    @classmethod
    def calc_engine_vram(cls, renderer, batch, textures, lighting,
                         sdf_cache, white_tex,
                         particles=None) -> float:
        """Calcola la VRAM usata dall'engine in MB. Cachata internamente."""
        cls._frame_counter += 1
        if cls._frame_counter % 30 != 1:
            return cls._vram_engine_mb

        total = 0

        # Renderer FBO textures
        for tex in (renderer.scene_texture, renderer.light_texture,
                    renderer.combine_texture):
            total += _tex_bytes(tex)

        # Renderer quad VBO
        total += renderer._quad_vbo.size

        # SpriteBatch
        total += batch._vbo.size + batch._ibo.size

        # TextureManager cache
        for tex in textures._cache.values():
            total += _tex_bytes(tex)

        # White texture
        total += _tex_bytes(white_tex)

        # LightingSystem
        total += lighting._vbo.size + lighting._ibo.size

        # SDF font cache
        for font in sdf_cache._cache.values():
            if hasattr(font, '_atlas') and font._atlas is not None:
                total += _tex_bytes(font._atlas)
            if hasattr(font, '_vbo'):
                total += font._vbo.size
            if hasattr(font, '_ibo'):
                total += font._ibo.size

        # Particles (opzionale)
        if particles is not None:
            total += particles._vbo.size + particles._ibo.size

        cls._vram_engine_mb = total / (1024 * 1024)
        return cls._vram_engine_mb

    # ------------------------------------------------------------------
    # GPU VRAM via GL extensions
    # ------------------------------------------------------------------

    @classmethod
    def query_gpu_vram(cls, ctx) -> tuple[float, float]:
        """Tenta di leggere VRAM GPU via estensioni GL.

        Returns:
            (total_mb, available_mb) -- (-1, -1) se non supportato.
        """
        if cls._gpu_queried and cls._frame_counter % 60 != 1:
            return cls._gpu_total_mb, cls._gpu_available_mb

        cls._gpu_queried = True

        if sys.platform != "win32":
            cls._gpu_total_mb = -1.0
            cls._gpu_available_mb = -1.0
            return cls._gpu_total_mb, cls._gpu_available_mb

        try:
            gl = ctypes.windll.opengl32
            val = ctypes.c_int(0)

            extensions = ctx.extensions if hasattr(ctx, 'extensions') else set()

            if 'GL_NVX_gpu_memory_info' in extensions:
                # NVIDIA -- valori in KB
                gl.glGetIntegerv(
                    cls._GL_GPU_MEM_INFO_TOTAL_AVAILABLE_MEM_NVX,
                    ctypes.byref(val))
                cls._gpu_total_mb = val.value / 1024.0

                gl.glGetIntegerv(
                    cls._GL_GPU_MEM_INFO_CURRENT_AVAILABLE_MEM_NVX,
                    ctypes.byref(val))
                cls._gpu_available_mb = val.value / 1024.0

            elif 'GL_ATI_meminfo' in extensions:
                # AMD -- primo int di un array di 4
                buf = (ctypes.c_int * 4)()
                gl.glGetIntegerv(cls._GL_TEXTURE_FREE_MEMORY_ATI, buf)
                cls._gpu_available_mb = buf[0] / 1024.0
                cls._gpu_total_mb = -1.0  # AMD non espone il totale

            else:
                cls._gpu_total_mb = -1.0
                cls._gpu_available_mb = -1.0

        except Exception as e:
            cprint.warning(e)
            cls._gpu_total_mb = -1.0
            cls._gpu_available_mb = -1.0

        return cls._gpu_total_mb, cls._gpu_available_mb
