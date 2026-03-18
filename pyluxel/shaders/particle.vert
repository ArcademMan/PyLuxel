#version 330 core

in vec2 in_position;
in vec2 in_uv;
in vec4 in_color;
in vec4 in_data;  // x = shape_type, y = param1, z = param2, w = reserved

uniform mat4 u_projection;

out vec2 v_uv;
out vec4 v_color;
flat out float v_shape;
flat out float v_param1;
flat out float v_param2;

void main() {
    gl_Position = u_projection * vec4(in_position, 0.0, 1.0);
    v_uv = in_uv;
    v_color = in_color;
    v_shape = in_data.x;
    v_param1 = in_data.y;
    v_param2 = in_data.z;
}
