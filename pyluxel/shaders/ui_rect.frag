#version 330 core

in vec2 v_uv;

uniform vec4 u_color;
uniform vec2 u_size;
uniform float u_radius;

out vec4 frag_color;

void main() {
    // Posizione in pixel rispetto al centro del rettangolo
    vec2 p = v_uv * u_size - u_size * 0.5;
    vec2 b = u_size * 0.5;

    // SDF rounded box
    vec2 q = abs(p) - b + u_radius;
    float dist = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - u_radius;

    // Anti-aliasing con smoothstep
    float alpha = 1.0 - smoothstep(-1.0, 1.0, dist);

    frag_color = vec4(u_color.rgb, u_color.a * alpha);
}
