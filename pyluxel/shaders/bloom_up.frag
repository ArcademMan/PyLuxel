#version 330 core

in vec2 v_uv;

uniform sampler2D u_texture;
uniform vec2 u_resolution;

out vec4 frag_color;

void main() {
    vec2 texel = 1.0 / u_resolution;

    // Dual kawase upsample: 9-tap tent filter
    vec3 sum = vec3(0.0);

    // Corner samples (weight 1)
    sum += texture(u_texture, v_uv + vec2(-1.0, -1.0) * texel).rgb;
    sum += texture(u_texture, v_uv + vec2( 1.0, -1.0) * texel).rgb;
    sum += texture(u_texture, v_uv + vec2(-1.0,  1.0) * texel).rgb;
    sum += texture(u_texture, v_uv + vec2( 1.0,  1.0) * texel).rgb;

    // Edge samples (weight 2)
    sum += texture(u_texture, v_uv + vec2(-1.0,  0.0) * texel).rgb * 2.0;
    sum += texture(u_texture, v_uv + vec2( 1.0,  0.0) * texel).rgb * 2.0;
    sum += texture(u_texture, v_uv + vec2( 0.0, -1.0) * texel).rgb * 2.0;
    sum += texture(u_texture, v_uv + vec2( 0.0,  1.0) * texel).rgb * 2.0;

    frag_color = vec4(sum / 12.0, 1.0);
}
