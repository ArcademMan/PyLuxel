from dataclasses import dataclass


@dataclass
class Theme:
    """Tema UI con colori neutri di default. Sovrascrivibile per qualsiasi progetto."""

    # Background (RGBA)
    bg: tuple = (0.22, 0.22, 0.24, 0.9)
    bg_hover: tuple = (0.30, 0.30, 0.33, 0.95)
    bg_disabled: tuple = (0.16, 0.16, 0.17, 0.6)

    # Accent bar (RGB)
    accent: tuple = (0.20, 0.50, 1.0)
    accent_width: float = 3.0
    accent_width_hover: float = 6.0

    # Testo (RGB)
    text: tuple = (0.85, 0.85, 0.85)
    text_hover: tuple = (1.0, 1.0, 1.0)
    text_disabled: tuple = (0.45, 0.45, 0.45)
    font_size: float = 20.0
    font_ref_height: float = 48.0

    # Slider
    track_color: tuple = (0.15, 0.15, 0.17, 1.0)
    track_height: float = 4.0
    handle_color: tuple = (0.20, 0.50, 1.0, 1.0)
    handle_size: float = 16.0

    # Toggle
    toggle_off: tuple = (0.30, 0.30, 0.33, 1.0)
    toggle_on: tuple = (0.20, 0.50, 1.0, 1.0)

    # Line edit
    cursor_color: tuple = (0.85, 0.85, 0.85, 1.0)
    selection_color: tuple = (0.15, 0.40, 0.85, 0.45)
    placeholder_color: tuple = (0.45, 0.45, 0.48, 1.0)

    # Padding interno widget
    padding: float = 12.0

    # Bordi arrotondati
    border_radius: float = 0.0

    # Animazione
    anim_speed: float = 10.0
