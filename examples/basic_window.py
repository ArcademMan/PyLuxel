"""Basic empty window -- the absolute minimum PyLuxel app."""

from pyluxel import App

app = App(1280, 720, "Basic Window")

app.set_post_process(ambient=1.0, vignette=0.0, bloom=0.0)

@app.on_draw
def draw():
    pass

app.run()
