"""Parallax background — layer di immagini a velocita' di scroll diverse."""

from __future__ import annotations
import moderngl
from typing import TYPE_CHECKING

from pyluxel.debug import cprint

if TYPE_CHECKING:
    from pyluxel.core.sprite_batch import SpriteBatch


class ParallaxLayer:
    """Un singolo layer parallax: un'immagine che scrolla a una velocita' relativa.

    scroll_speed:
        0.0 = fermo (sfondo fisso, es. cielo)
        0.5 = scrolla al 50% della camera (montagne lontane)
        1.0 = segue la camera 1:1 (livello del gioco)
    """

    def __init__(self, texture: moderngl.Texture,
                 scroll_speed: float = 0.5,
                 repeat_x: bool = True,
                 repeat_y: bool = False,
                 offset_y: float = 0.0):
        self.texture = texture
        self.scroll_speed = scroll_speed
        self.repeat_x = repeat_x
        self.repeat_y = repeat_y
        self.offset_y = offset_y

        self.tex_width, self.tex_height = texture.size


class ParallaxBackground:
    """Gestisce una pila di ParallaxLayer ordinati dal piu' lontano al piu' vicino.

    Uso tipico:
        bg = ParallaxBackground()
        bg.add(sky_tex, scroll_speed=0.0)
        bg.add(mountains_tex, scroll_speed=0.2)
        bg.add(trees_tex, scroll_speed=0.5)

        # Nel game loop:
        bg.render(batch, camera.x, camera.y, design_width, design_height)
    """

    def __init__(self):
        self.layers: list[ParallaxLayer] = []

    def add(self, texture: moderngl.Texture,
            scroll_speed: float = 0.5,
            repeat_x: bool = True,
            repeat_y: bool = False,
            offset_y: float = 0.0) -> ParallaxLayer:
        """Aggiunge un layer parallax. I layer vengono disegnati nell'ordine di aggiunta."""
        layer = ParallaxLayer(texture, scroll_speed, repeat_x, repeat_y, offset_y)
        self.layers.append(layer)
        return layer

    def remove(self, layer: ParallaxLayer) -> None:
        """Rimuove un layer parallax."""
        try:
            self.layers.remove(layer)
        except ValueError as e:
            cprint.error(e)

    def clear(self) -> None:
        """Rimuove tutti i layer parallax."""
        self.layers.clear()

    @property
    def layer_count(self) -> int:
        """Ritorna il numero di layer."""
        return len(self.layers)

    def render(self, batch: SpriteBatch,
               camera_x: float, camera_y: float,
               screen_w: float, screen_h: float) -> None:
        """Renderizza tutti i layer parallax nel batch.

        Per ogni layer, chiama batch.begin(texture) e batch.end().
        I layer con repeat_x vengono ripetuti orizzontalmente per coprire lo schermo.

        Args:
            batch: SpriteBatch da usare
            camera_x, camera_y: posizione corrente della camera
            screen_w, screen_h: dimensioni viewport in design pixels
        """
        for layer in self.layers:
            batch.begin(layer.texture)
            self._render_layer(batch, layer, camera_x, camera_y, screen_w, screen_h)
            batch.end()

    def _render_layer(self, batch: SpriteBatch, layer: ParallaxLayer,
                      cam_x: float, cam_y: float,
                      screen_w: float, screen_h: float) -> None:
        """Renderizza un singolo layer con ripetizione opzionale."""
        tw = layer.tex_width
        th = layer.tex_height

        if tw <= 0 or th <= 0:
            return

        # Offset basato sulla camera e scroll speed
        offset_x = cam_x * layer.scroll_speed
        offset_y = cam_y * layer.scroll_speed + layer.offset_y

        if layer.repeat_x:
            # Calcola la posizione iniziale per coprire tutto lo schermo
            start_x = -(offset_x % tw)
            x = start_x
            while x < screen_w:
                if layer.repeat_y:
                    start_y = -(offset_y % th)
                    y = start_y
                    while y < screen_h:
                        batch.draw(x, y, tw, th)
                        y += th
                else:
                    y = screen_h - th - offset_y
                    batch.draw(x, y, tw, th)
                x += tw
        else:
            # Singola immagine
            x = -offset_x
            if layer.repeat_y:
                start_y = -(offset_y % th)
                y = start_y
                while y < screen_h:
                    batch.draw(x, y, tw, th)
                    y += th
            else:
                y = screen_h - th - offset_y
                batch.draw(x, y, tw, th)
