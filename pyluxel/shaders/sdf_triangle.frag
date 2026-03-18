#version 330 core

in vec2 v_local;

uniform vec2 u_shape_half;
uniform vec4 u_color;

out vec4 frag_color;

// Inigo Quilez - sdTriangleIsosceles
// q = (half_base_width, height), apex at origin, base at y = q.y
float sdTriangleIsosceles(vec2 p, vec2 q) {
    p.x = abs(p.x);
    vec2 a = p - q * clamp(dot(p, q) / dot(q, q), 0.0, 1.0);
    vec2 b = p - q * vec2(clamp(p.x / q.x, 0.0, 1.0), 1.0);
    float s = -sign(q.y);
    vec2 d = min(vec2(dot(a, a), s * (p.x * q.y - p.y * q.x)),
                 vec2(dot(b, b), s * (p.y - q.y)));
    return -sqrt(d.x) * sign(d.y);
}

void main() {
    float hw = u_shape_half.x;
    float hh = u_shape_half.y;

    // Apex al top (y negativo in design space), base in basso
    // Trasla l'apice all'origine per la formula IQ
    vec2 p = v_local;
    p.y += hh;

    float dist = sdTriangleIsosceles(p, vec2(hw, hh * 2.0));

    float aa = fwidth(dist) * 0.75;
    float alpha = 1.0 - smoothstep(-aa, aa, dist);

    frag_color = vec4(u_color.rgb, u_color.a * alpha);
}
