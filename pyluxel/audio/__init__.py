"""pyluxel.audio -- Gestione centralizzata audio: SFX, musica e audio spaziale 2D."""

from pyluxel.audio.manager import SoundManager

Sound = SoundManager()

__all__ = [
    "SoundManager",
    "Sound",
]
