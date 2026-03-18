#version 330 core

uniform mat4 u_projection;

in vec2 in_pos;

void main() {
    gl_Position = u_projection * vec4(in_pos, 0.0, 1.0);
}
