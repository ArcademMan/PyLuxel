"""pyluxel.shaders -- Bundled GLSL shaders + shared loader utility."""

from importlib import resources


def load_shader(filename: str) -> str:
    """Carica un file shader bundled con il pacchetto pyluxel."""
    return resources.files("pyluxel.shaders").joinpath(filename).read_text(encoding="utf-8")
