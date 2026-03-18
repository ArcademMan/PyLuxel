#version 330 core

in vec2 v_uv;
in vec4 v_color;
flat in float v_shape;
flat in float v_param1;   // ring: thickness | star: inner_ratio
flat in float v_param2;   // star: num points

out vec4 frag_color;

void main() {
    vec2 c = v_uv * 2.0 - 1.0;  // remap 0..1 -> -1..1
    float alpha;

    if (v_shape < 0.5) {
        // --- CIRCLE (shape 0) ---
        float dist = length(c);
        alpha = 1.0 - smoothstep(0.5, 1.0, dist);
    }
    else if (v_shape < 1.5) {
        // --- SQUARE (shape 1) ---
        float d = max(abs(c.x), abs(c.y));
        alpha = 1.0 - smoothstep(0.6, 1.0, d);
    }
    else if (v_shape < 2.5) {
        // --- SPARK (shape 2) ---
        float ax = abs(c.x);
        float ay = abs(c.y);
        float core = smoothstep(0.4, 0.0, ay) * (1.0 - smoothstep(0.3, 1.0, ax));
        float center = exp(-6.0 * (ax * ax + ay * ay * 4.0));
        alpha = max(core, center);
    }
    else if (v_shape < 3.5) {
        // --- RING (shape 3) ---
        float dist = length(c);
        float inner = v_param1;
        float ring = smoothstep(inner - 0.1, inner, dist) * (1.0 - smoothstep(0.8, 1.0, dist));
        alpha = ring;
    }
    else if (v_shape < 4.5) {
        // --- STAR (shape 4) ---
        int n = int(v_param2 + 0.5);
        float ir = v_param1;
        float an = 3.141593 / float(n);
        float bn = mod(atan(c.x, -c.y) + an, 2.0 * an) - an;
        float len = length(c);
        vec2 q = vec2(cos(bn), abs(sin(bn))) * len;
        vec2 A = vec2(0.9, 0.0);
        vec2 B = vec2(0.9 * ir * cos(an), 0.9 * ir * sin(an));
        vec2 AB = B - A;
        vec2 AQ = q - A;
        float t = clamp(dot(AQ, AB) / dot(AB, AB), 0.0, 1.0);
        float dist = length(AQ - AB * t);
        float cross_val = AB.x * AQ.y - AB.y * AQ.x;
        float sd = -dist * sign(cross_val);
        alpha = 1.0 - smoothstep(-0.05, 0.05, sd);
    }
    else if (v_shape < 5.5) {
        // --- DIAMOND (shape 5) ---
        float d = abs(c.x) + abs(c.y);
        alpha = 1.0 - smoothstep(0.6, 1.0, d);
    }
    else if (v_shape < 6.5) {
        // --- TRIANGLE (shape 6) ---
        vec2 p = c;
        p.y += 0.3;
        p.x = abs(p.x);
        float d = max(
            p.x * 0.866 + p.y * 0.5,
            -p.y + 0.3
        );
        alpha = 1.0 - smoothstep(0.5, 0.7, d);
    }
    else {
        // --- SOFT DOT (shape 7) ---
        float dist2 = dot(c, c);
        alpha = exp(-4.0 * dist2);
    }

    frag_color = vec4(v_color.rgb, v_color.a * alpha);
}
