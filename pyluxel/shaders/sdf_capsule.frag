#version 330 core

in vec2 v_local;

uniform vec2 u_shape_half;
uniform vec4 u_color;

out vec4 frag_color;

void main() {
    float hw = u_shape_half.x;
    float hh = u_shape_half.y;

    // Capsule SDF: distanza dalla superficie della capsula
    float dist;
    if (hw >= hh) {
        // Capsula orizzontale
        float dx = max(abs(v_local.x) - (hw - hh), 0.0);
        dist = length(vec2(dx, v_local.y)) - hh;
    } else {
        // Capsula verticale
        float dy = max(abs(v_local.y) - (hh - hw), 0.0);
        dist = length(vec2(v_local.x, dy)) - hw;
    }

    // Anti-aliasing screen-space via derivate
    float aa = fwidth(dist) * 0.75;
    float alpha = 1.0 - smoothstep(-aa, aa, dist);

    frag_color = vec4(u_color.rgb, u_color.a * alpha);
}
