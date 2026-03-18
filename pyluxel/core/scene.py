"""pyluxel.core.scene -- Scene manager per organizzare stati di gioco.

Ogni Scene e' un contesto indipendente con i propri hook (setup, update,
draw, draw_overlay, ecc.). Lo SceneManager gestisce lo stack di scene
e delega le chiamate alla scena attiva.

Uso tipico:

    class MenuScene(Scene):
        def setup(self):
            ...
        def update(self, dt):
            if start_pressed:
                self.manager.switch(GameScene)
        def draw_overlay(self):
            app.draw_text("MENU", 640, 360, size=48)

    class GameScene(Scene):
        def setup(self):
            ...
        def update(self, dt):
            ...

    app = MyApp(1280, 720, "Game")
    app.scenes.register("menu", MenuScene)
    app.scenes.register("game", GameScene)
    app.scenes.switch("menu")
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyluxel.app import App


class Scene:
    """Stato di gioco. Override dei metodi necessari.

    Attributi disponibili dopo l'attach:
        self.app     -- riferimento all'App
        self.manager -- riferimento allo SceneManager
    """

    app: App
    manager: SceneManager

    def setup(self):
        """Chiamato una volta quando la scena viene attivata per la prima volta."""
        pass

    def enter(self):
        """Chiamato ogni volta che la scena diventa attiva (anche dopo un pop)."""
        pass

    def exit(self):
        """Chiamato quando la scena viene disattivata (switch o push di un'altra)."""
        pass

    def update(self, dt: float):
        """Logica di gioco."""
        pass

    def draw(self):
        """Rendering scena (scene FBO)."""
        pass

    def draw_lights(self):
        """Luci dinamiche (light FBO)."""
        pass

    def shadow_casters(self):
        """Occluder per ombre."""
        pass

    def draw_overlay(self):
        """HUD/UI sopra post-processing."""
        pass

    def handle_event(self, event):
        """Evento pygame raw."""
        pass


class SceneManager:
    """Gestisce uno stack di scene.

    - switch(name): cambia scena (svuota lo stack)
    - push(name): mette una scena sopra la corrente
    - pop(): torna alla scena precedente
    """

    def __init__(self, app: App):
        self._app = app
        self._registry: dict[str, type[Scene]] = {}
        self._stack: list[Scene] = []
        self._instances: dict[str, Scene] = {}
        self._setup_done: set[str] = set()

    @property
    def current(self) -> Scene | None:
        """La scena attiva (cima dello stack)."""
        return self._stack[-1] if self._stack else None

    @property
    def stack_depth(self) -> int:
        """Numero di scene nello stack."""
        return len(self._stack)

    def register(self, name: str, scene_class: type[Scene]):
        """Registra una classe Scene con un nome."""
        self._registry[name] = scene_class

    def _get_or_create(self, name: str) -> Scene:
        """Ottieni l'istanza della scena (crea al primo uso)."""
        if name not in self._instances:
            cls = self._registry.get(name)
            if cls is None:
                raise KeyError(f"Scena '{name}' non registrata. "
                               f"Usa manager.register('{name}', MiaScena)")
            instance = cls()
            instance.app = self._app
            instance.manager = self
            self._instances[name] = instance
        return self._instances[name]

    def switch(self, name: str):
        """Cambia alla scena indicata, svuotando lo stack."""
        # Exit di tutte le scene nello stack
        for scene in reversed(self._stack):
            scene.exit()
        self._stack.clear()

        scene = self._get_or_create(name)
        self._stack.append(scene)
        if name not in self._setup_done:
            scene.setup()
            self._setup_done.add(name)
        scene.enter()

    def push(self, name: str):
        """Metti una scena sopra la corrente (la corrente resta nello stack)."""
        if self._stack:
            self._stack[-1].exit()

        scene = self._get_or_create(name)
        self._stack.append(scene)
        if name not in self._setup_done:
            scene.setup()
            self._setup_done.add(name)
        scene.enter()

    def pop(self):
        """Rimuovi la scena corrente e torna alla precedente."""
        if self._stack:
            self._stack[-1].exit()
            self._stack.pop()
        if self._stack:
            self._stack[-1].enter()

    def reset(self, name: str):
        """Forza il re-setup della scena alla prossima attivazione."""
        self._setup_done.discard(name)
        self._instances.pop(name, None)

    # ── Deleghe (chiamate da App.run) ────────────────────────────────

    def update(self, dt: float):
        if self._stack:
            self._stack[-1].update(dt)

    def draw(self):
        if self._stack:
            self._stack[-1].draw()

    def draw_lights(self):
        if self._stack:
            self._stack[-1].draw_lights()

    def shadow_casters(self):
        if self._stack:
            self._stack[-1].shadow_casters()

    def draw_overlay(self):
        if self._stack:
            self._stack[-1].draw_overlay()

    def handle_event(self, event):
        if self._stack:
            self._stack[-1].handle_event(event)
