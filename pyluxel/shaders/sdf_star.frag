#version 330 core

in vec2 v_local;

uniform vec2 u_shape_half;
uniform vec4 u_color;
uniform int u_points;
uniform float u_inner_ratio;

out vec4 frag_color;

// SDF stella a N punte con raggi alternati outer/inner
// Primo vertice (outer) punta in alto (-y in design space)
float sdStar(vec2 p, float R, float ir, int n) {
    float an = 3.141593 / float(n);
    float r = R * ir;

    // Riduce al primo settore (primo vertice outer in alto)
    float bn = mod(atan(p.x, -p.y) + an, 2.0 * an) - an;
    float len = length(p);
    vec2 q = vec2(cos(bn), abs(sin(bn))) * len;

    // Edge da outer vertex (R, 0) a inner vertex (r*cos(an), r*sin(an))
    vec2 A = vec2(R, 0.0);
    vec2 B = vec2(r * cos(an), r * sin(an));
    vec2 AB = B - A;
    vec2 AQ = q - A;

    float t = clamp(dot(AQ, AB) / dot(AB, AB), 0.0, 1.0);
    float dist = length(AQ - AB * t);

    // Segno via cross product (positivo = dentro)
    float cross_val = AB.x * AQ.y - AB.y * AQ.x;
    return -dist * sign(cross_val);
}

void main() {
    float R = u_shape_half.x;

    float dist = sdStar(v_local, R, u_inner_ratio, u_points);

    float aa = fwidth(dist) * 0.75;
    float alpha = 1.0 - smoothstep(-aa, aa, dist);

    frag_color = vec4(u_color.rgb, u_color.a * alpha);
}
