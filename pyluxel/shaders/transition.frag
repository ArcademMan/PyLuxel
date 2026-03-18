#version 330 core

in vec2 v_uv;

uniform sampler2D u_texture;       // scena corrente
uniform float u_progress;          // 0.0 = nessuna transizione, 1.0 = completata
uniform int u_mode;                // 0=fade, 1=dissolve, 2=wipe_left, 3=wipe_down, 4=diamond
uniform vec3 u_color;              // colore di fade/dissolve
uniform vec2 u_resolution;

out vec4 frag_color;

// Hash noise per dissolve
float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

void main() {
    vec4 scene = texture(u_texture, v_uv);
    float p = u_progress;

    float mask = 0.0;

    if (u_mode == 0) {
        // Fade: semplice alpha blend al colore
        mask = p;
    }
    else if (u_mode == 1) {
        // Dissolve: noise threshold
        float noise = hash12(v_uv * u_resolution * 0.5);
        mask = step(noise, p);
    }
    else if (u_mode == 2) {
        // Wipe left: tende da destra a sinistra
        float edge = p * 1.2;  // un po' di margine
        float softness = 0.05;
        mask = smoothstep(edge - softness, edge + softness, 1.0 - v_uv.x);
    }
    else if (u_mode == 3) {
        // Wipe down: tende dall'alto in basso
        float edge = p * 1.2;
        float softness = 0.05;
        mask = smoothstep(edge - softness, edge + softness, v_uv.y);
    }
    else if (u_mode == 4) {
        // Diamond: pattern a diamante dal centro
        vec2 centered = abs(v_uv - 0.5) * 2.0;
        float diamond = centered.x + centered.y;
        mask = smoothstep(p * 2.2 - 0.1, p * 2.2 + 0.1, diamond);
        mask = 1.0 - mask;
    }

    vec3 result = mix(scene.rgb, u_color, mask);
    frag_color = vec4(result, 1.0);
}
