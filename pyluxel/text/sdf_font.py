import struct
import os
import numpy as np
import pygame
import moderngl

from pyluxel.debug import cprint

# --- SDF Atlas Parameters ---
ATLAS_FONT_SIZE = 48   # base font size in the atlas (design pixels)
RENDER_MULT = 4        # render glyphs at this multiple for precise SDF
SDF_SPREAD = 8         # spread in render-space pixels (becomes 2px in atlas)
GLYPH_PAD = 2          # padding between glyphs in atlas to prevent bleed

CHARS = [chr(c) for c in range(32, 127)]

# Binary cache format magic
_CACHE_MAGIC = b"SDF1"


def _compute_sdf(alpha, spread):
    """Compute Signed Distance Field from an alpha channel array.

    Returns float32 array with values 0..1 where 0.5 = edge of glyph.
    > 0.5 = inside, < 0.5 = outside.
    """
    h, w = alpha.shape
    binary = alpha > 128

    padded = np.pad(binary, spread, mode='constant', constant_values=False)

    offsets = []
    for dy in range(-spread, spread + 1):
        for dx in range(-spread, spread + 1):
            d_sq = dy * dy + dx * dx
            if d_sq <= spread * spread:
                offsets.append((dy, dx, d_sq))

    n_offsets = len(offsets)
    d_sq_values = np.array([o[2] for o in offsets], dtype=np.float32)

    shifted_stack = np.empty((n_offsets, h, w), dtype=np.bool_)
    for i, (dy, dx, _) in enumerate(offsets):
        shifted_stack[i] = padded[spread + dy:spread + dy + h,
                                  spread + dx:spread + dx + w]

    edge_mask = binary[np.newaxis, :, :] != shifted_stack

    max_d = np.float32(spread * spread + 1)
    d_sq_grid = np.where(edge_mask,
                         d_sq_values[:, np.newaxis, np.newaxis],
                         max_d)
    min_d_sq = np.min(d_sq_grid, axis=0)
    min_dist = np.sqrt(min_d_sq)

    sdf = np.where(binary, min_dist, -min_dist)
    sdf = sdf / (2.0 * spread) + 0.5
    return np.clip(sdf, 0.0, 1.0).astype(np.float32)


def _downsample(arr, factor):
    """Area-average downsampling by integer factor."""
    h, w = arr.shape
    new_h = h // factor
    new_w = w // factor
    trimmed = arr[:new_h * factor, :new_w * factor]
    return trimmed.reshape(new_h, factor, new_w, factor).mean(axis=(1, 3))


def _get_cache_path(font_name, cache_dir):
    """Return path to the binary .dat cache file for this font."""
    safe_name = font_name.replace("/", "_").replace("\\", "_").replace(" ", "_")
    return os.path.join(cache_dir, safe_name + ".dat")


def _save_cache(font_name, atlas_uint8, atlas_glyph_h, widths_atlas, uv_map,
                cache_dir):
    """Save SDF atlas and metadata as a single binary .dat file.

    Format:
        4B  magic "SDF1"
        I   atlas_w
        I   atlas_h
        I   glyph_h
        I   num_chars
        per char:
            B   char code (ASCII)
            I   glyph width
            4f  u0, v0, u1, v1
        raw atlas pixels (atlas_h * atlas_w bytes, uint8)
    """
    os.makedirs(cache_dir, exist_ok=True)
    dat_path = _get_cache_path(font_name, cache_dir)

    h, w = atlas_uint8.shape
    chars = sorted(widths_atlas.keys())

    with open(dat_path, "wb") as f:
        # Header
        f.write(_CACHE_MAGIC)
        f.write(struct.pack("<IIII", w, h, atlas_glyph_h, len(chars)))

        # Per-character metadata
        for ch in chars:
            glyph_w = widths_atlas[ch]
            u0, v0, u1, v1 = uv_map[ch]
            f.write(struct.pack("<BI4f", ord(ch), glyph_w, u0, v0, u1, v1))

        # Raw atlas pixel data
        f.write(atlas_uint8.tobytes())


def _load_cache(font_name, cache_dir):
    """Load cached SDF atlas from binary .dat file.
    Returns (atlas_uint8, atlas_glyph_h, widths_atlas, uv_map) or None.
    """
    dat_path = _get_cache_path(font_name, cache_dir)
    if not os.path.exists(dat_path):
        return None

    try:
        with open(dat_path, "rb") as f:
            # Verify magic
            magic = f.read(4)
            if magic != _CACHE_MAGIC:
                return None

            # Header
            header = f.read(16)
            if len(header) < 16:
                cprint.warning(f"SDF cache truncated header: {dat_path}")
                return None
            atlas_w, atlas_h, glyph_h, num_chars = struct.unpack("<IIII", header)

            # Sanity check
            if num_chars > 256 or atlas_w > 16384 or atlas_h > 16384:
                cprint.warning(f"SDF cache has invalid values: {dat_path}")
                return None

            # Per-character metadata
            widths = {}
            uv_map = {}
            char_size = struct.calcsize("<BI4f")
            for _ in range(num_chars):
                data = f.read(char_size)
                if len(data) < char_size:
                    cprint.warning(f"SDF cache truncated char data: {dat_path}")
                    return None
                code, gw, u0, v0, u1, v1 = struct.unpack("<BI4f", data)
                ch = chr(code)
                widths[ch] = gw
                uv_map[ch] = (u0, v0, u1, v1)

            # Raw atlas pixels
            expected = atlas_h * atlas_w
            raw = f.read(expected)
            if len(raw) < expected:
                cprint.warning(f"SDF cache truncated atlas data: {dat_path}")
                return None
            atlas_uint8 = np.frombuffer(raw, dtype=np.uint8).reshape(atlas_h, atlas_w)

        return atlas_uint8, glyph_h, widths, uv_map
    except (OSError, struct.error, ValueError) as e:
        cprint.warning(f"SDF cache load failed for {dat_path}: {e}")
        return None


class SDFFont:
    """SDF font: atlas generated once, cached to disk, rendered via shader.

    First launch: generates SDF atlas (slow), saves to cache_dir.
    Subsequent launches: loads cached atlas from disk (instant).
    """

    def __init__(self, ctx: moderngl.Context, sdf_prog: moderngl.Program,
                 font_name: str, cache_dir: str = "sdf_cache"):
        self.ctx = ctx
        self.prog = sdf_prog

        # Compute cap-height center offset for visual centering
        from pyluxel.text.fonts import FontManager
        fm = FontManager()
        render_size = ATLAS_FONT_SIZE * RENDER_MULT
        hi_font = fm.get(font_name, render_size)
        ascent = hi_font.get_ascent()
        cap_height = ascent  # fallback
        metrics = hi_font.metrics("H")
        if metrics and metrics[0]:
            cap_height = metrics[0][3]  # maxy = pixels above baseline
        # Distance from quad top to cap-height visual center (in atlas space)
        self._cap_center_atlas = (SDF_SPREAD + ascent - cap_height * 0.5) / RENDER_MULT

        # Try loading from disk cache first
        cached = _load_cache(font_name, cache_dir)
        if cached is not None:
            atlas_uint8, atlas_glyph_h, widths_atlas, uv_map = cached
            self._atlas_glyph_h = atlas_glyph_h
            self._widths_atlas = widths_atlas
            self._uv_map = uv_map
        else:
            # Generate SDF atlas from scratch
            atlas_uint8, atlas_glyph_h, widths_atlas, uv_map = self._generate(font_name)
            self._atlas_glyph_h = atlas_glyph_h
            self._widths_atlas = widths_atlas
            self._uv_map = uv_map

            # Save to disk for next time
            _save_cache(font_name, atlas_uint8, atlas_glyph_h, widths_atlas, uv_map,
                        cache_dir)

        # Upload atlas to GPU
        h, w = atlas_uint8.shape
        atlas_flipped = np.ascontiguousarray(np.flipud(atlas_uint8))
        self.atlas = ctx.texture((w, h), 1, atlas_flipped.tobytes())
        self.atlas.filter = (moderngl.LINEAR, moderngl.LINEAR)

        # VAO for batched text rendering
        max_chars = 2048
        self._vertex_data = np.zeros(max_chars * 4 * 8, dtype="f4")
        self._vbo = ctx.buffer(reserve=self._vertex_data.nbytes, dynamic=True)

        indices = []
        for i in range(max_chars):
            b = i * 4
            indices.extend([b, b + 1, b + 2, b + 2, b + 3, b])
        self._ibo = ctx.buffer(np.array(indices, dtype="i4").tobytes())

        self._vao = ctx.vertex_array(
            sdf_prog,
            [(self._vbo, "2f 2f 4f", "in_position", "in_uv", "in_color")],
            index_buffer=self._ibo,
        )
        self._count = 0

    def _generate(self, font_name):
        """Generate SDF atlas from scratch. Returns (atlas_uint8, glyph_h, widths, uv_map)."""
        render_size = ATLAS_FONT_SIZE * RENDER_MULT
        spread = SDF_SPREAD

        from pyluxel.text.fonts import FontManager
        fm = FontManager()
        hi_font = fm.get(font_name, render_size)

        raw_glyphs = {}
        max_render_h = 0
        for ch in CHARS:
            surf = hi_font.render(ch, True, (255, 255, 255))
            raw_glyphs[ch] = surf
            max_render_h = max(max_render_h, surf.get_height())

        padded_h = max_render_h + 2 * spread

        sdf_glyphs = {}
        for ch in CHARS:
            surf = raw_glyphs[ch]
            w_r, h_r = surf.get_size()
            padded_w = w_r + 2 * spread

            padded_surf = pygame.Surface((padded_w, padded_h), pygame.SRCALPHA)
            padded_surf.fill((0, 0, 0, 0))
            y_off = spread + (max_render_h - h_r) // 2
            padded_surf.blit(surf, (spread, y_off))

            alpha = pygame.surfarray.array_alpha(padded_surf).T
            sdf_hr = _compute_sdf(alpha, spread)
            sdf_ds = _downsample(sdf_hr, RENDER_MULT)
            sdf_glyphs[ch] = sdf_ds

        atlas_glyph_h = padded_h // RENDER_MULT

        widths_atlas = {}
        for ch in CHARS:
            widths_atlas[ch] = sdf_glyphs[ch].shape[1]

        total_w = sum(g.shape[1] + GLYPH_PAD for g in sdf_glyphs.values())
        atlas = np.zeros((atlas_glyph_h, total_w), dtype=np.float32)

        uv_map = {}
        x_cursor = 0
        for ch in CHARS:
            g = sdf_glyphs[ch]
            gh, gw = g.shape
            gh = min(gh, atlas_glyph_h)
            atlas[:gh, x_cursor:x_cursor + gw] = g[:gh]

            u0 = x_cursor / total_w
            u1 = (x_cursor + gw) / total_w
            uv_map[ch] = (u0, 0.0, u1, 1.0)

            x_cursor += gw + GLYPH_PAD

        atlas_uint8 = (atlas * 255).astype(np.uint8)
        return atlas_uint8, atlas_glyph_h, widths_atlas, uv_map

    def _scale_for_size(self, size: float) -> float:
        return size / ATLAS_FONT_SIZE

    def get_glyph_width(self, char: str, size: float) -> float:
        """Ritorna la larghezza di un singolo glifo alla dimensione data."""
        s = self._scale_for_size(size)
        return self._widths_atlas.get(char, 0) * s

    def get_line_height(self, size: float) -> float:
        """Ritorna l'altezza di una riga alla dimensione data."""
        return self._atlas_glyph_h * self._scale_for_size(size)

    def has_char(self, char: str) -> bool:
        """True se il carattere e' supportato dall'atlas."""
        return char in self._uv_map

    def measure(self, text: str, size: float) -> tuple[float, float]:
        s = self._scale_for_size(size)
        line_h = self._atlas_glyph_h * s
        lines = text.split("\n")
        max_w = max(
            (sum(self._widths_atlas.get(ch, 0) for ch in line) * s for line in lines),
            default=0.0,
        )
        h = line_h * len(lines)
        return (max_w, h)

    def draw(self, text: str, x: float, y: float, size: float,
             r: float = 1.0, g: float = 1.0, b: float = 1.0, a: float = 1.0,
             align_x: str = "left", align_y: str = "top"):
        s = self._scale_for_size(size)
        widths = self._widths_atlas
        uv_map = self._uv_map
        quad_h = self._atlas_glyph_h * s

        lines = text.split("\n")

        if align_y == "center":
            y -= self._cap_center_atlas * s + quad_h * (len(lines) - 1) * 0.5
        elif align_y == "bottom":
            y -= quad_h * len(lines)

        space_w = widths.get(" ", 4) * s
        vd = self._vertex_data

        for line in lines:
            line_x = x
            if align_x != "left":
                tw = sum(widths.get(ch, 0) for ch in line) * s
                if align_x == "center":
                    line_x -= tw * 0.5
                elif align_x == "right":
                    line_x -= tw

            cursor_x = line_x
            for ch in line:
                if ch not in uv_map:
                    ch = "?"
                if ch == " ":
                    cursor_x += space_w
                    continue

                u0, v0, u1, v1 = uv_map[ch]
                quad_w = widths[ch] * s

                if self._count >= 2048:
                    self.flush()

                i = self._count * 32
                cy = y + quad_h
                cx2 = cursor_x + quad_w
                vd[i]     = cursor_x; vd[i+1] = cy;  vd[i+2] = u0; vd[i+3] = v0
                vd[i+4]   = r;       vd[i+5] = g;    vd[i+6] = b;  vd[i+7] = a
                vd[i+8]   = cx2;     vd[i+9] = cy;   vd[i+10]= u1; vd[i+11]= v0
                vd[i+12]  = r;       vd[i+13]= g;    vd[i+14]= b;  vd[i+15]= a
                vd[i+16]  = cx2;     vd[i+17]= y;    vd[i+18]= u1; vd[i+19]= v1
                vd[i+20]  = r;       vd[i+21]= g;    vd[i+22]= b;  vd[i+23]= a
                vd[i+24]  = cursor_x;vd[i+25]= y;    vd[i+26]= u0; vd[i+27]= v1
                vd[i+28]  = r;       vd[i+29]= g;    vd[i+30]= b;  vd[i+31]= a
                self._count += 1

                cursor_x += quad_w
            y += quad_h

    def flush(self):
        if self._count == 0:
            return

        self.atlas.use(0)
        self.prog["u_texture"].value = 0

        self._vbo.write(self._vertex_data[:self._count * 32].tobytes())
        self._vao.render(moderngl.TRIANGLES, vertices=self._count * 6)

        from pyluxel.debug.gpu_stats import GPUStats
        GPUStats.record_draw(self._count)

        self._count = 0

    def release(self):
        for obj in (self._vao, self._vbo, self._ibo, self.atlas):
            try:
                obj.release()
            except Exception as e:
                cprint.warning("GPU release failed:", e)


class SDFFontCache:
    """Cache: un SDFFont per font family. Ogni font scala a qualsiasi size via shader."""

    _instance: "SDFFontCache | None" = None

    def __init__(self, ctx: moderngl.Context, sdf_prog: moderngl.Program,
                 cache_dir: str = "sdf_cache"):
        self.ctx = ctx
        self.prog = sdf_prog
        self._cache_dir = cache_dir
        self._cache: dict[str, SDFFont] = {}
        SDFFontCache._instance = self

    @classmethod
    def instance(cls) -> "SDFFontCache":
        """Ritorna l'istanza corrente di SDFFontCache."""
        if cls._instance is None:
            raise RuntimeError("SDFFontCache non inizializzato. Crea un App o un SDFFontCache prima.")
        return cls._instance

    def get(self, font_name: str) -> SDFFont:
        if font_name not in self._cache:
            self._cache[font_name] = SDFFont(
                self.ctx, self.prog, font_name, cache_dir=self._cache_dir)
        return self._cache[font_name]

    def list_cached_fonts(self) -> list[str]:
        """Ritorna la lista dei nomi font caricati in cache."""
        return list(self._cache.keys())

    def clear(self):
        for f in self._cache.values():
            try:
                f.release()
            except Exception as e:
                cprint.warning("SDF cache release failed:", e)
        self._cache.clear()

    def release(self):
        self.clear()
