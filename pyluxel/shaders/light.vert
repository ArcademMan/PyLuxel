#version 330 core

in vec2 in_position;
in vec2 in_uv;
in vec4 in_light_data;  // rgb = color, a = intensity
in vec4 in_extra;       // falloff_mode, is_spotlight, cos_half_angle, direction_rad
in vec4 in_light_world; // center_x, center_y, light_z, atlas_row
in vec3 in_inner_params; // inner_radius_ratio, cos_inner_half_angle, cone_base_trunc

uniform mat4 u_projection;

out vec2 v_uv;
out vec3 v_light_color;
out float v_intensity;
flat out vec4 v_extra;
flat out vec4 v_light_world;
flat out vec3 v_inner_params;
out vec2 v_frag_world;   // posizione del vertice in design space

void main() {
    gl_Position = u_projection * vec4(in_position, 0.0, 1.0);
    v_uv = in_uv;
    v_light_color = in_light_data.rgb;
    v_intensity = in_light_data.a;
    v_extra = in_extra;
    v_light_world = in_light_world;
    v_inner_params = in_inner_params;
    v_frag_world = in_position;  // design space position
}
