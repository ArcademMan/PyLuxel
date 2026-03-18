#version 330 core

in vec2 v_uv;

uniform sampler2D u_scene;
uniform sampler2D u_lightmap;
uniform float u_ambient;
uniform float u_max_exposure;  // max light value (default 1.5)

out vec4 frag_color;

void main() {
    vec4 scene = texture(u_scene, v_uv);
    vec4 light = texture(u_lightmap, v_uv);

    // Mix ambient + dynamic lighting
    vec3 total_light = vec3(u_ambient) + light.rgb;
    total_light = clamp(total_light, 0.0, u_max_exposure);

    frag_color = vec4(scene.rgb * total_light, scene.a);
}
