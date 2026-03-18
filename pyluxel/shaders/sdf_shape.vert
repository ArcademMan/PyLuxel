#version 330 core

uniform mat4 u_projection;
uniform vec2 u_center;
uniform vec2 u_half_size;
uniform float u_angle;

in vec2 in_pos;

out vec2 v_local;

void main() {
    v_local = in_pos * u_half_size;
    float c = cos(u_angle);
    float s = sin(u_angle);
    vec2 rotated = vec2(v_local.x * c - v_local.y * s,
                        v_local.x * s + v_local.y * c);
    gl_Position = u_projection * vec4(u_center + rotated, 0.0, 1.0);
}
