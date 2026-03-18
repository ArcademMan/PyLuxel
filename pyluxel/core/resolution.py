"""
Resolution Manager — singleton per scaling dinamico della risoluzione.

Tutta la logica di gioco/UI usa una 'design resolution' di base (default 1280x720).
Il singleton Resolution fornisce helper per scalare i valori in pixel alla
risoluzione reale della finestra, così testo, elementi di gioco e UI crescono
proporzionalmente.

Esempio d'uso:
    from pygame_scaler import R

    # All'avvio (opzionale, default 1280x720)
    R.init(1280, 720)

    # Quando si crea/ridimensiona la finestra
    R.set_resolution(1920, 1080)

    # Nel codice UI — tutti i valori sono in "pixel di design"
    button_w = R.s(200)       # -> 300 px a 1920x1080
    button_h = R.s(50)        # -> 75 px
    x = R.center_x - R.s(100) # centrato orizzontalmente
    radius = R.sf(33.5)       # -> 50.25 (float, per calcoli precisi)
"""
from typing import Optional, Tuple, List


class Resolution:
    """Singleton che mantiene la risoluzione corrente e il fattore di scala."""

    _instance: Optional['Resolution'] = None

    BASE_WIDTH: int = 1280
    BASE_HEIGHT: int = 720

    PRESETS: List[Tuple[int, int]] = [
        (1280, 720),
        (1600, 900),
        (1920, 1080),
        (2560, 1440),
    ]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._width = cls.BASE_WIDTH
            cls._instance._height = cls.BASE_HEIGHT
        return cls._instance

    # --- Configurazione ---

    @classmethod
    def init(cls, base_width: int = 1280, base_height: int = 720,
             presets: Optional[List[Tuple[int, int]]] = None) -> 'Resolution':
        """Configura la design resolution di base e (opzionalmente) i preset.

        Chiamare all'avvio, prima di set_resolution().
        Ritorna l'istanza singleton per comodità.
        """
        cls.BASE_WIDTH = base_width
        cls.BASE_HEIGHT = base_height
        if presets is not None:
            cls.PRESETS = presets
        inst = cls()
        inst._width = base_width
        inst._height = base_height
        return inst

    # --- Proprietà ---

    @property
    def width(self) -> int:
        """Larghezza corrente della finestra in pixel."""
        return self._width

    @property
    def height(self) -> int:
        """Altezza corrente della finestra in pixel."""
        return self._height

    @property
    def center_x(self) -> int:
        """Centro orizzontale in design space."""
        return self.BASE_WIDTH // 2

    @property
    def center_y(self) -> int:
        """Centro verticale in design space."""
        return self.BASE_HEIGHT // 2

    @property
    def scale(self) -> float:
        """Fattore di scala: width_corrente / BASE_WIDTH."""
        return self._width / self.BASE_WIDTH

    # --- Scaling helpers ---

    def s(self, value: float) -> int:
        """Scala un valore in pixel di design alla risoluzione corrente (intero).

        Usare per dimensioni, posizioni, spaziature — tutto ciò che serve come int.
        """
        return int(value * self.scale)

    def sf(self, value: float) -> float:
        """Scala un valore in pixel di design alla risoluzione corrente (float).

        Usare per calcoli matematici dove serve precisione (angoli, raggi, ecc.).
        """
        return value * self.scale

    # --- Risoluzione nativa ---

    @staticmethod
    def get_native_resolution() -> Tuple[int, int]:
        """Ottieni la risoluzione nativa del monitor via pygame."""
        import pygame
        sizes = pygame.display.get_desktop_sizes()
        return sizes[0] if sizes else (1920, 1080)

    @staticmethod
    def native_in_presets() -> bool:
        """Controlla se la risoluzione nativa è fra i preset."""
        native = Resolution.get_native_resolution()
        return native in Resolution.PRESETS

    # --- Mutatore ---

    def set_resolution(self, width: int, height: int) -> None:
        """Aggiorna la risoluzione corrente.

        Chiamare prima di (ri)creare il display pygame.
        Dopo questa chiamata, tutti i valori R.s() useranno il nuovo scale.
        """
        self._width = width
        self._height = height

    def get_base_resolution(self) -> tuple[int, int]:
        """Ritorna la design resolution di base (BASE_WIDTH, BASE_HEIGHT)."""
        return self.BASE_WIDTH, self.BASE_HEIGHT

    def unscale(self, screen_value: float) -> float:
        """Converte un valore in pixel schermo in pixel di design (inverso di s/sf)."""
        sc = self.scale
        if sc <= 0:
            return screen_value
        return screen_value / sc
