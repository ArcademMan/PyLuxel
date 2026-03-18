#version 330 core

in vec2 v_local;

uniform vec2 u_shape_half;
uniform vec4 u_color;

out vec4 frag_color;

void main() {
    float dist = length(v_local) - u_shape_half.x;

    float aa = fwidth(dist) * 0.75;
    float alpha = 1.0 - smoothstep(-aa, aa, dist);

    frag_color = vec4(u_color.rgb, u_color.a * alpha);
}
