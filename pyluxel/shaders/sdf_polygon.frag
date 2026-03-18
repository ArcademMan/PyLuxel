#version 330 core

in vec2 v_local;

uniform vec2 u_shape_half;
uniform vec4 u_color;
uniform int u_sides;

out vec4 frag_color;

// Inigo Quilez - sdPolygon (regular convex polygon)
// Primo vertice punta in alto (-y in design space)
float sdPolygon(vec2 p, float r, int n) {
    float an = 3.141593 / float(n);
    vec2 acs = vec2(cos(an), sin(an));

    // Riduce al primo settore (primo vertice in alto)
    float bn = mod(atan(p.x, -p.y), 2.0 * an) - an;
    p = length(p) * vec2(cos(bn), abs(sin(bn)));

    // Distanza dal lato
    p -= r * acs;
    p.y += clamp(-p.y, 0.0, r * acs.y);
    return length(p) * sign(p.x);
}

void main() {
    float r = u_shape_half.x;

    float dist = sdPolygon(v_local, r, u_sides);

    float aa = fwidth(dist) * 0.75;
    float alpha = 1.0 - smoothstep(-aa, aa, dist);

    frag_color = vec4(u_color.rgb, u_color.a * alpha);
}
