"""pyluxel.effects -- Effetti visivi: lighting, fog, particles."""

from pyluxel.effects.lighting import Light, LightingSystem
from pyluxel.effects.fog import FogLayer
from pyluxel.effects.particles import (
    ParticleSystem, ParticlePreset,
    SHAPE_CIRCLE, SHAPE_SQUARE, SHAPE_SPARK, SHAPE_RING,
    SHAPE_STAR, SHAPE_DIAMOND, SHAPE_TRIANGLE, SHAPE_SOFT_DOT,
    FIRE, SMOKE, EXPLOSION, SPARK_SHOWER, RAIN,
    SNOW, MAGIC, BLOOD, DUST, STEAM,
)

__all__ = [
    "Light",
    "LightingSystem",
    "FogLayer",
    "ParticleSystem",
    "ParticlePreset",
    "SHAPE_CIRCLE", "SHAPE_SQUARE", "SHAPE_SPARK", "SHAPE_RING",
    "SHAPE_STAR", "SHAPE_DIAMOND", "SHAPE_TRIANGLE", "SHAPE_SOFT_DOT",
    "FIRE", "SMOKE", "EXPLOSION", "SPARK_SHOWER", "RAIN",
    "SNOW", "MAGIC", "BLOOD", "DUST", "STEAM",
]
