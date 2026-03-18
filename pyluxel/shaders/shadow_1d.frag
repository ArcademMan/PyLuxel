#version 330 core

in vec2 v_uv;

uniform sampler2D u_occlusion_map;
uniform vec2 u_light_center;   // posizione luce in design space
uniform vec2 u_resolution;      // design resolution (es. 1280x720)
uniform float u_max_distance;   // raggio della luce

out vec4 frag_color;

const int MAX_STEPS = 256;
const float PI = 3.14159265359;

void main() {
    // Ogni pixel X corrisponde a un angolo [0..2pi]
    float angle = v_uv.x * 2.0 * PI;
    vec2 ray_dir = vec2(cos(angle), sin(angle));

    // Step size dinamico: copre l'intero raggio in MAX_STEPS
    float step_size = u_max_distance / float(MAX_STEPS);

    float distance_found = u_max_distance;

    for (int i = 1; i <= MAX_STEPS; i++) {
        float d = float(i) * step_size;
        vec2 pos = u_light_center + ray_dir * d;

        // Converti in UV per campionare l'occlusion map
        vec2 sample_uv = pos / u_resolution;
        sample_uv.y = 1.0 - sample_uv.y;  // flip Y per OpenGL

        // Fuori dai bordi = nessuna occlusione
        if (sample_uv.x < 0.0 || sample_uv.x > 1.0 ||
            sample_uv.y < 0.0 || sample_uv.y > 1.0) {
            break;
        }

        // Se alpha > 0.5, abbiamo colpito un occluder
        float occlusion = texture(u_occlusion_map, sample_uv).a;
        if (occlusion > 0.5) {
            distance_found = d;
            break;
        }
    }

    // Normalizza la distanza [0..1]
    float normalized = distance_found / u_max_distance;
    frag_color = vec4(normalized, 0.0, 0.0, 1.0);
}
