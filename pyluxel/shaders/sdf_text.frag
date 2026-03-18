#version 330 core

in vec2 v_uv;
in vec4 v_color;

uniform sampler2D u_texture;
uniform float u_smoothing;  // multiplier for fwidth smoothing (default 1.0)

out vec4 frag_color;

void main() {
    float dist = texture(u_texture, v_uv).r;

    // fwidth() computes screen-space rate of change for pixel-perfect AA.
    // u_smoothing scales the band: <1.0 = sharper, >1.0 = softer
    float smoothing = fwidth(dist) * u_smoothing;
    float alpha = smoothstep(0.5 - smoothing, 0.5 + smoothing, dist);

    frag_color = vec4(v_color.rgb, v_color.a * alpha);
}
