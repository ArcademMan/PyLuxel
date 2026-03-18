#version 330 core

in vec2 v_local;

uniform vec2 u_shape_half;
uniform vec4 u_color;

out vec4 frag_color;

void main() {
    vec2 d = abs(v_local) - u_shape_half;
    float dist = length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);

    float aa = fwidth(dist) * 0.75;
    float alpha = 1.0 - smoothstep(-aa, aa, dist);

    frag_color = vec4(u_color.rgb, u_color.a * alpha);
}
