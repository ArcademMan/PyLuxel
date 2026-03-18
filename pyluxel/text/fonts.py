"""
Font Manager — singleton per caricare e cachare font pygame scalati.

Gestisce font custom (.ttf) con nomi semantici e cache automatica.
Alla risoluzione cambiata, basta chiamare clear_cache() e i font
verranno ricaricati alle nuove dimensioni al prossimo get().

Esempio d'uso:
    from pyluxel import R, FontManager

    # All'avvio — indica dove sono i file .ttf
    FontManager.init("assets/fonts", font_files={
        "body": "MyFont-Regular.ttf",
        "title": "MyFont-Bold.ttf",
    })

    # Nel codice UI
    fm = FontManager()
    title_font = fm.get(fm.TITLE, R.s(48))
    body_font = fm.get(fm.BODY, R.s(16))

    # Al cambio risoluzione
    fm.clear_cache()
"""
import pygame
from typing import Optional

from pyluxel.core import paths
from pyluxel.core.pak import asset_open, asset_exists
from pyluxel.debug import cprint


class FontManager:
    """Singleton che carica, cacha e serve font custom.

    Per cambiare font, modifica _FONT_FILES o usa register().
    """

    _instance: Optional['FontManager'] = None
    _initialized: bool = False

    # Nomi semantici di default
    BODY = "body"
    BODY_BOLD = "body_bold"
    TITLE = "title"

    # Mappatura: nome semantico -> file .ttf (vuoto di default, il gioco configura via init)
    _FONT_FILES: dict[str, str] = {}

    _fonts_dir: str = ""

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if FontManager._initialized:
            return
        FontManager._initialized = True
        self._cache: dict[tuple[str, int], pygame.font.Font] = {}

    # --- Configurazione ---

    @classmethod
    def init(cls, fonts_dir: str,
             font_files: Optional[dict[str, str]] = None) -> 'FontManager':
        """Configura la cartella dei font e (opzionalmente) la mappatura.

        Args:
            fonts_dir: percorso alla cartella contenente i file .ttf
            font_files: dict {nome_semantico: "NomeFile.ttf"} (opzionale,
                        sovrascrive la mappatura di default)

        Returns:
            L'istanza singleton per comodità.
        """
        cls._fonts_dir = fonts_dir
        if font_files is not None:
            cls._FONT_FILES = font_files
        inst = cls()
        inst._cache.clear()
        return inst

    # --- API principale ---

    def get(self, name: str, size: int) -> pygame.font.Font:
        """Ottieni un font cachato per nome semantico e dimensione.

        Ritorna il font custom se disponibile, altrimenti il font di default pygame.
        """
        key = (name, size)
        if key not in self._cache:
            self._cache[key] = self._load(name, size)
        return self._cache[key]

    def clear_cache(self) -> None:
        """Invalida tutti i font cachati (chiamare dopo cambio risoluzione)."""
        self._cache.clear()

    def list_registered_fonts(self) -> list[str]:
        """Ritorna la lista dei nomi font registrati."""
        return list(self._FONT_FILES.keys())

    def is_font_registered(self, name: str) -> bool:
        """True se il nome font e' registrato."""
        return name in self._FONT_FILES

    def register(self, name: str, filename: str) -> None:
        """Registra una nuova mappatura nome -> file .ttf.

        Invalida le entry in cache per questo nome, così verranno ricaricate.
        """
        self._FONT_FILES[name] = filename
        keys_to_remove = [k for k in self._cache if k[0] == name]
        for k in keys_to_remove:
            del self._cache[k]

    # --- Interno ---

    def _load(self, name: str, size: int) -> pygame.font.Font:
        """Carica un font da file .ttf, con fallback al font di default."""
        filename = self._FONT_FILES.get(name)
        if filename:
            path = paths.join(self._fonts_dir, filename)
            if asset_exists(path):
                try:
                    return pygame.font.Font(asset_open(path), size)
                except pygame.error as e:
                    cprint.warning(f"Cannot load font '{path}':", e)
            else:
                cprint.warning(f"Font file not found: {path}")
        else:
            cprint.warning(f"Unknown font name '{name}'")
        cprint.info(f"Using fallback font for '{name}' size {size}")
        return pygame.font.Font(None, size)
