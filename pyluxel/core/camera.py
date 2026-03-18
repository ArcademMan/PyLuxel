class Camera:
    """Camera 2D con smooth follow e clamping ai bordi della mappa."""

    def __init__(self, design_width: int = 1280, design_height: int = 720):
        self.design_width = design_width
        self.design_height = design_height
        self.x = 0.0
        self.y = 0.0
        self._shake_x = 0.0
        self._shake_y = 0.0
        self._zoom = 1.0

    def update(self, target_x: float, target_y: float,
               map_width: float, map_height: float,
               dt: float = 0.0, smoothing: float = 0.0):
        """Aggiorna la camera verso il target.

        Args:
            target_x, target_y: posizione del target (centro schermo)
            map_width, map_height: dimensioni della mappa in pixel
            dt: delta time in secondi (necessario per smooth follow)
            smoothing: 0.0 = snap istantaneo, 1.0+ = piu' lento (lerp speed)
        """
        # Reset shake ogni frame (va ri-applicato se serve)
        self._shake_x = 0.0
        self._shake_y = 0.0

        vw = self.design_width / self._zoom
        vh = self.design_height / self._zoom

        goal_x = target_x - vw / 2
        goal_y = target_y - vh / 2

        # Clamp ai bordi (gestisce anche mappa piu' piccola del viewport)
        if map_width <= vw:
            goal_x = (map_width - vw) / 2
        else:
            goal_x = max(0.0, min(goal_x, map_width - vw))

        if map_height <= vh:
            goal_y = (map_height - vh) / 2
        else:
            goal_y = max(0.0, min(goal_y, map_height - vh))

        # Smooth follow (lerp) o snap istantaneo
        if smoothing > 0.0 and dt > 0.0:
            import math
            speed = 1.0 - math.exp(-dt / (smoothing * 0.1))
            self.x += (goal_x - self.x) * speed
            self.y += (goal_y - self.y) * speed
        else:
            self.x = goal_x
            self.y = goal_y

    def apply(self, world_x: float, world_y: float) -> tuple[float, float]:
        """Converte coordinate mondo → coordinate schermo."""
        return ((world_x - self.x - self._shake_x) * self._zoom,
                (world_y - self.y - self._shake_y) * self._zoom)

    def set_position(self, x: float, y: float):
        """Imposta direttamente la posizione della camera (snap senza follow)."""
        self.x = x
        self.y = y

    def get_bounds(self) -> tuple[float, float, float, float]:
        """Ritorna i bordi del viewport in coordinate mondo (left, top, right, bottom)."""
        vw = self.design_width / self._zoom
        vh = self.design_height / self._zoom
        return (self.x + self._shake_x,
                self.y + self._shake_y,
                self.x + self._shake_x + vw,
                self.y + self._shake_y + vh)

    def screen_to_world(self, screen_x: float, screen_y: float) -> tuple[float, float]:
        """Converte coordinate schermo → coordinate mondo (inverso di apply)."""
        return (screen_x / self._zoom + self.x + self._shake_x,
                screen_y / self._zoom + self.y + self._shake_y)

    def reset_shake(self):
        """Azzera lo shake immediatamente."""
        self._shake_x = 0.0
        self._shake_y = 0.0

    def shake(self, intensity: float = 5.0):
        """Applica screen shake casuale. Chiamare dopo update(), si resetta ogni frame."""
        import random
        self._shake_x = random.uniform(-intensity, intensity)
        self._shake_y = random.uniform(-intensity, intensity)

    def set_zoom(self, zoom: float):
        """Imposta il livello di zoom. 1.0 = default, >1 = zoom in, <1 = zoom out."""
        self._zoom = max(0.1, zoom)

    def get_zoom(self) -> float:
        """Restituisce il livello di zoom corrente."""
        return self._zoom
