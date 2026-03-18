#version 330 core

in vec2 v_uv;
in vec3 v_light_color;
in float v_intensity;
flat in vec4 v_extra;       // falloff_mode, is_spotlight, cos_half_angle, direction_rad
flat in vec4 v_light_world; // center_x, center_y, light_z, atlas_row
flat in vec3 v_inner_params; // inner_radius_ratio, cos_inner_half_angle, cone_base_trunc
in vec2 v_frag_world;       // fragment position in design space

uniform sampler2D u_normal_map;
uniform float u_normal_enabled;  // 0.0 = off, 1.0 = on
uniform vec2 u_resolution;       // design resolution

// Shadow mapping (atlas)
uniform sampler2D u_shadow_map;   // shadow map atlas (720 x N)
uniform float u_shadow_enabled;   // 0.0 = off, 1.0 = on
uniform float u_shadow_softness;  // penumbra (0.01 = duro, 0.1 = morbido)
uniform float u_atlas_height;     // altezza atlas (es. 64.0)

out vec4 frag_color;

void main() {
    // Direzione dal centro del quad al frammento ([-1,1])
    vec2 centered = v_uv * 2.0 - 1.0;
    float dist = length(centered);

    // Inner radius: nessuna luce dentro inner_ratio
    float inner_ratio = v_inner_params.x;
    if (dist < inner_ratio) {
        discard;
    }

    // Remap da [inner_ratio, 1] a [0, 1]
    float remapped = (dist - inner_ratio) / max(1.0 - inner_ratio, 0.001);

    // Attenuazione radiale base
    float attenuation = 1.0 - smoothstep(0.0, 1.0, remapped);

    // Falloff configurabile
    int falloff_mode = int(v_extra.x + 0.5);
    if (falloff_mode == 0) {
        // Linear - gia' ok
    } else if (falloff_mode == 2) {
        // Cubic
        attenuation = attenuation * attenuation * attenuation;
    } else {
        // Quadratic (default)
        attenuation *= attenuation;
    }

    // Spotlight cone
    bool is_spotlight = v_extra.y > 0.5;
    if (is_spotlight && dist > 0.001) {
        float cos_half_angle = v_extra.z;  // outer cone
        float dir_rad = v_extra.w;
        float cos_inner = v_inner_params.y;   // inner cone (sfumatura bordo)
        float trunc = v_inner_params.z;       // cone_base: 0=punta, 1=rettangolo

        // Direzione spotlight
        vec2 spot_dir = vec2(cos(dir_rad), sin(dir_rad));

        float spot_factor;

        if (trunc > 0.001) {
            // Trapezoid mode (cone_base > 0): forma trapezoidale
            float along = dot(centered, spot_dir);
            vec2 perp_vec = centered - spot_dir * along;
            float perp = length(perp_vec);

            float sin_half = sqrt(max(1.0 - cos_half_angle * cos_half_angle, 0.0));
            float tan_half = sin_half / max(cos_half_angle, 0.001);

            float max_perp = tan_half * (trunc + max(along, 0.0) * (1.0 - trunc));

            float edge = max(max_perp * 0.08, 0.01);
            spot_factor = 1.0 - smoothstep(max_perp - edge, max_perp + edge, perp);
            spot_factor *= smoothstep(-0.01, 0.02, along);
        } else {
            // Standard cone mode
            vec2 frag_dir = normalize(centered);
            float cos_angle = dot(frag_dir, spot_dir);

            if (cos_inner < 0.9999) {
                // Inner/outer cone: piena intensita' dentro inner, sfumatura verso outer
                spot_factor = smoothstep(cos_half_angle, cos_inner, cos_angle);
            } else {
                // Default soft edge
                float edge_softness = 0.05;
                spot_factor = smoothstep(
                    cos_half_angle - edge_softness,
                    cos_half_angle + edge_softness,
                    cos_angle
                );
            }
        }

        attenuation *= spot_factor;
    }

    // Normal mapping
    float normal_factor = 1.0;
    if (u_normal_enabled > 0.5) {
        // Sample normal map usando la posizione del frammento in screen UV
        vec2 screen_uv = gl_FragCoord.xy / u_resolution;
        // Flip Y perche' OpenGL ha Y invertito rispetto al design space
        screen_uv.y = 1.0 - screen_uv.y;
        vec4 normal_sample = texture(u_normal_map, screen_uv);

        // Se c'e' un normal map (alpha > 0), applica illuminazione direzionale
        if (normal_sample.a > 0.1) {
            // Decodifica normale tangent-space: (0..1) -> (-1..1)
            vec3 normal = normal_sample.rgb * 2.0 - 1.0;
            normal = normalize(normal);

            // Direzione dal frammento alla luce in design space
            vec2 light_center = v_light_world.xy;
            float light_z = v_light_world.z;

            vec3 light_dir = normalize(vec3(
                light_center.x - v_frag_world.x,
                light_center.y - v_frag_world.y,
                light_z
            ));

            // Flip Y della luce per matching con tangent-space
            light_dir.y = -light_dir.y;

            // Calcolo diffuso Lambert
            float ndotl = max(dot(normal, light_dir), 0.0);
            normal_factor = ndotl;
        }
    }

    // Shadow mapping (atlas)
    float shadow_factor = 1.0;
    if (u_shadow_enabled > 0.5) {
        vec2 to_frag = v_frag_world - v_light_world.xy;

        // Angolo dal centro luce al frammento [0..1]
        float angle_rad = atan(to_frag.y, to_frag.x);
        float angle_uv = fract(angle_rad / 6.28318530718);

        // Campiona la riga corretta nell'atlas
        float atlas_row = v_light_world.w;
        float atlas_v = (atlas_row + 0.5) / u_atlas_height;
        float shadow_norm = texture(u_shadow_map, vec2(angle_uv, atlas_v)).r;

        // Confronto in spazio normalizzato (dist e' gia' frag_dist / radius)
        shadow_factor = 1.0 - smoothstep(
            shadow_norm - u_shadow_softness,
            shadow_norm + u_shadow_softness,
            dist
        );
    }

    frag_color = vec4(v_light_color * v_intensity * attenuation * normal_factor * shadow_factor, attenuation);
}
