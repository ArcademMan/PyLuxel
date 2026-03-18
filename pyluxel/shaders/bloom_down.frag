#version 330 core

in vec2 v_uv;

uniform sampler2D u_texture;
uniform vec2 u_resolution;
uniform float u_threshold;  // >0 solo per il primo passo (estrazione bright)

out vec4 frag_color;

void main() {
    vec2 texel = 1.0 / u_resolution;

    // Dual kawase downsample: 13-tap (center + 4 bilinear)
    vec3 center = texture(u_texture, v_uv).rgb * 4.0;

    vec3 sum = center;
    sum += texture(u_texture, v_uv + vec2(-1.0, -1.0) * texel).rgb;
    sum += texture(u_texture, v_uv + vec2( 1.0, -1.0) * texel).rgb;
    sum += texture(u_texture, v_uv + vec2(-1.0,  1.0) * texel).rgb;
    sum += texture(u_texture, v_uv + vec2( 1.0,  1.0) * texel).rgb;

    sum += texture(u_texture, v_uv + vec2(-2.0, -2.0) * texel).rgb;
    sum += texture(u_texture, v_uv + vec2( 2.0, -2.0) * texel).rgb;
    sum += texture(u_texture, v_uv + vec2(-2.0,  2.0) * texel).rgb;
    sum += texture(u_texture, v_uv + vec2( 2.0,  2.0) * texel).rgb;

    vec3 color = sum / 12.0;

    // Threshold (solo primo passo)
    if (u_threshold > 0.0) {
        float brightness = dot(color, vec3(0.2126, 0.7152, 0.0722));
        color *= max(brightness - u_threshold, 0.0) / max(brightness, 0.001);
    }

    frag_color = vec4(color, 1.0);
}
