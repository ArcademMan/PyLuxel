#version 330 core

in vec2 v_uv;
out vec4 fragColor;

uniform float u_time;
uniform vec2  u_wind_speed;   // (0.5, 0.1) default
uniform vec3  u_color;        // fog tint
uniform float u_density;      // 0..1
uniform float u_scale;        // noise zoom
uniform float u_sparsity;     // 0 = uniform fog, 1 = isolated banks
uniform float u_height_falloff; // 0 = uniform, >0 = piu' denso in basso
uniform vec2  u_resolution;   // design size for aspect correction

// --- Simplex 2D noise (hash-based, no texture) ---

vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec2 mod289(vec2 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec3 permute(vec3 x) { return mod289(((x * 34.0) + 1.0) * x); }

float snoise(vec2 v) {
    const vec4 C = vec4(
        0.211324865405187,   // (3.0 - sqrt(3.0)) / 6.0
        0.366025403784439,   // 0.5 * (sqrt(3.0) - 1.0)
       -0.577350269189626,   // -1.0 + 2.0 * C.x
        0.024390243902439    // 1.0 / 41.0
    );

    // First corner
    vec2 i  = floor(v + dot(v, C.yy));
    vec2 x0 = v - i + dot(i, C.xx);

    // Other corners
    vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
    vec4 x12 = x0.xyxy + C.xxzz;
    x12.xy -= i1;

    // Permutations
    i = mod289(i);
    vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0))
                             + i.x + vec3(0.0, i1.x, 1.0));

    vec3 m = max(0.5 - vec3(dot(x0, x0), dot(x12.xy, x12.xy),
                             dot(x12.zw, x12.zw)), 0.0);
    m = m * m;
    m = m * m;

    // Gradients
    vec3 x  = 2.0 * fract(p * C.www) - 1.0;
    vec3 h  = abs(x) - 0.5;
    vec3 ox = floor(x + 0.5);
    vec3 a0 = x - ox;

    m *= 1.79284291400159 - 0.85373472095314 * (a0 * a0 + h * h);

    vec3 g;
    g.x = a0.x * x0.x  + h.x * x0.y;
    g.yz = a0.yz * x12.xz + h.yz * x12.yw;

    return 130.0 * dot(m, g);
}

// --- FBM (4 octaves) ---

float fbm(vec2 p) {
    float value = 0.0;
    float amp   = 0.5;
    float freq  = 1.0;
    for (int i = 0; i < 4; i++) {
        value += amp * snoise(p * freq);
        freq  *= 2.0;
        amp   *= 0.5;
    }
    return value;
}

void main() {
    // Aspect-corrected UV
    vec2 uv = v_uv;
    float aspect = u_resolution.x / u_resolution.y;
    uv.x *= aspect;

    // Apply scale and wind offset
    vec2 pos = uv * u_scale + u_wind_speed * u_time;

    // Two FBM layers for richer look
    float n1 = fbm(pos);
    float n2 = fbm(pos * 1.7 + vec2(5.2, 1.3));

    // Combine: remap from [-1,1] to [0,1]
    float fog = (n1 + n2) * 0.5 + 0.5;

    // Smooth shaping — sparsity controls threshold
    float edge_lo = 0.2 + u_sparsity * 0.35;
    float edge_hi = 0.8 - u_sparsity * 0.15;
    fog = smoothstep(edge_lo, edge_hi, fog);
    fog *= u_density;

    // Height-based falloff: piu' denso in basso (v_uv.y=1 e' il basso)
    if (u_height_falloff > 0.0) {
        float height_factor = 1.0 - exp(-(1.0 - v_uv.y) * u_height_falloff);
        fog *= height_factor;
    }

    fragColor = vec4(u_color, fog);
}
