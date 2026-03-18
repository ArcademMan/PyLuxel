"""pyluxel.input -- Gestione input centralizzata con action mapping."""

from pyluxel.input.manager import InputManager, InputDevice, Mouse, Pad, Stick

Input = InputManager()

__all__ = [
    "InputManager",
    "InputDevice",
    "Input",
    "Mouse",
    "Pad",
    "Stick",
]
