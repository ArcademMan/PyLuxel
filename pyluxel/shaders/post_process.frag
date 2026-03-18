#version 330 core

in vec2 v_uv;

// Textures
uniform sampler2D u_texture;        // combined scene (HDR)
uniform sampler2D u_bloom_texture;  // bloom result
uniform sampler2D u_lut;            // color grading LUT (1024x32 strip)

// Basic effects
uniform float u_vignette_strength;
uniform float u_bloom_intensity;
uniform float u_exposure;
uniform float u_tone_mapping;       // 0=none, 1=reinhard, 2=aces

// Toggleable effects
uniform float u_chromatic_aberration;
uniform float u_film_grain;
uniform float u_crt_enabled;
uniform float u_crt_curvature;
uniform float u_crt_scanline;
uniform float u_lut_enabled;

// Shockwave distortion
uniform int   u_num_shockwaves;
uniform vec2  u_shockwave_centers[8];
uniform vec4  u_shockwave_params[8];  // radius, thickness, strength, 0

// Heat haze
uniform int   u_num_hazes;
uniform vec4  u_haze_rects[4];        // x, y, w, h (in pixel design space)
uniform vec4  u_haze_params[4];       // strength, speed, scale, 0

// God rays
uniform float u_god_rays;
uniform vec2  u_god_rays_source;      // posizione UV della sorgente
uniform float u_god_rays_decay;
uniform float u_god_rays_density;

// Globals
uniform vec2  u_resolution;
uniform float u_time;

out vec4 frag_color;


// ===================== Tone Mapping =====================

vec3 aces_tonemap(vec3 x) {
    const float a = 2.51;
    const float b = 0.03;
    const float c = 2.43;
    const float d = 0.59;
    const float e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}

vec3 reinhard_tonemap(vec3 x) {
    return x / (x + vec3(1.0));
}


// ===================== CRT =====================

vec2 crt_distort(vec2 uv, float curvature) {
    vec2 centered = uv * 2.0 - 1.0;
    float r2 = dot(centered, centered);
    centered *= 1.0 + r2 * curvature;
    return centered * 0.5 + 0.5;
}


// ===================== Film Grain Noise =====================

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}


// ===================== Color Grading LUT =====================

vec3 apply_lut(vec3 color) {
    const float LUT_SIZE = 32.0;

    color = clamp(color, 0.0, 1.0);

    float blue = color.b * (LUT_SIZE - 1.0);
    float blue_floor = floor(blue);
    float blue_fract = blue - blue_floor;

    vec2 uv0 = vec2(
        (color.r * (LUT_SIZE - 1.0) + blue_floor * LUT_SIZE + 0.5)
            / (LUT_SIZE * LUT_SIZE),
        (color.g * (LUT_SIZE - 1.0) + 0.5) / LUT_SIZE
    );
    vec2 uv1 = vec2(
        (color.r * (LUT_SIZE - 1.0) + min(blue_floor + 1.0, LUT_SIZE - 1.0)
            * LUT_SIZE + 0.5) / (LUT_SIZE * LUT_SIZE),
        uv0.y
    );

    return mix(texture(u_lut, uv0).rgb, texture(u_lut, uv1).rgb, blue_fract);
}


// ===================== Main =====================

void main() {
    vec2 uv = v_uv;

    // --- 1. CRT barrel distortion ---
    if (u_crt_enabled > 0.5) {
        uv = crt_distort(uv, u_crt_curvature);
        if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
            frag_color = vec4(0.0, 0.0, 0.0, 1.0);
            return;
        }
    }

    // --- 2. Shockwave distortion ---
    for (int i = 0; i < u_num_shockwaves; i++) {
        vec2 pixel_pos = uv * u_resolution;
        vec2 delta = pixel_pos - u_shockwave_centers[i];
        float dist = length(delta);

        float radius    = u_shockwave_params[i].x;
        float thickness = u_shockwave_params[i].y;
        float strength  = u_shockwave_params[i].z;

        float ring = abs(dist - radius);
        if (ring < thickness) {
            float factor = (1.0 - ring / thickness);
            factor *= factor;  // quadratic falloff
            uv += normalize(delta) * factor * strength / u_resolution;
        }
    }

    // --- 2b. Heat haze distortion ---
    for (int i = 0; i < u_num_hazes; i++) {
        vec4 rect = u_haze_rects[i];  // x, y, w, h in pixels
        vec2 pixel_pos = uv * u_resolution;

        // Controlla se il frammento e' dentro la zona
        vec2 local = pixel_pos - rect.xy;
        if (local.x >= 0.0 && local.x <= rect.z &&
            local.y >= 0.0 && local.y <= rect.w) {
            float strength = u_haze_params[i].x;
            float speed    = u_haze_params[i].y;
            float scale    = u_haze_params[i].z;

            // Soft edges (fade ai bordi della zona)
            float fade_x = smoothstep(0.0, rect.z * 0.15, local.x)
                         * smoothstep(0.0, rect.z * 0.15, rect.z - local.x);
            float fade_y = smoothstep(0.0, rect.w * 0.2, local.y)
                         * smoothstep(0.0, rect.w * 0.1, rect.w - local.y);
            float fade = fade_x * fade_y;

            // Distorsione ondulata
            float wave = sin(local.y / scale + u_time * speed)
                       * cos(local.x / (scale * 1.3) + u_time * speed * 0.7);
            uv.x += wave * strength * fade;
            uv.y += wave * strength * 0.5 * fade;
        }
    }

    // --- 3. Chromatic aberration + sample ---
    vec3 color;
    if (u_chromatic_aberration > 0.0) {
        vec2 centered = uv - 0.5;
        float dist2 = dot(centered, centered);
        float offset = dist2 * u_chromatic_aberration * 0.02;

        color.r = texture(u_texture, uv + centered * offset).r;
        color.g = texture(u_texture, uv).g;
        color.b = texture(u_texture, uv - centered * offset).b;
    } else {
        color = texture(u_texture, uv).rgb;
    }

    // --- 4. Add bloom ---
    if (u_bloom_intensity > 0.0) {
        vec3 bloom = texture(u_bloom_texture, uv).rgb;
        color += bloom * u_bloom_intensity;
    }

    // --- 4b. God rays ---
    if (u_god_rays > 0.0 && u_bloom_intensity > 0.0) {
        const int NUM_SAMPLES = 64;
        vec2 ray_uv = uv;
        vec2 to_source = u_god_rays_source - ray_uv;
        vec2 delta = to_source * u_god_rays_density / float(NUM_SAMPLES);
        float illum_decay = 1.0;
        vec3 rays = vec3(0.0);
        float total_weight = 0.0;

        for (int i = 0; i < NUM_SAMPLES; i++) {
            ray_uv += delta;
            // Campiona dalla bloom texture (gia' sfocata, solo aree luminose)
            vec3 s = texture(u_bloom_texture, ray_uv).rgb;
            float w = illum_decay;
            rays += s * w;
            total_weight += w;
            illum_decay *= u_god_rays_decay;
        }

        // Fade ai bordi: raggi piu' deboli lontano dalla sorgente
        float dist_to_source = length(uv - u_god_rays_source);
        float distance_fade = 1.0 - smoothstep(0.0, 1.2, dist_to_source);

        color += (rays / total_weight) * u_god_rays * distance_fade * 2.0;
    }

    // --- 5. Exposure ---
    color *= u_exposure;

    // --- 6. Tone mapping ---
    if (u_tone_mapping > 1.5) {
        color = aces_tonemap(color);
    } else if (u_tone_mapping > 0.5) {
        color = reinhard_tonemap(color);
    }

    // --- 7. Color grading LUT ---
    if (u_lut_enabled > 0.5) {
        color = apply_lut(color);
    }

    // --- 8. Vignette ---
    if (u_vignette_strength > 0.0) {
        vec2 vig_uv = v_uv - 0.5;
        float vignette = 1.0 - dot(vig_uv, vig_uv) * u_vignette_strength;
        color *= clamp(vignette, 0.0, 1.0);
    }

    // --- 9. Film grain ---
    if (u_film_grain > 0.0) {
        float grain = hash12(gl_FragCoord.xy + fract(u_time) * 1000.0);
        color += (grain - 0.5) * u_film_grain;
    }

    // --- 10. CRT scanlines ---
    if (u_crt_enabled > 0.5) {
        float scanline = sin(v_uv.y * u_resolution.y * 3.14159265) * 0.5 + 0.5;
        color *= mix(1.0, scanline, u_crt_scanline);
    }

    frag_color = vec4(max(color, vec3(0.0)), 1.0);
}
