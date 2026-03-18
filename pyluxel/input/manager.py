"""Input Manager — action-based input abstraction.

Maps logical actions to physical inputs (keyboard, mouse, controller).
Singleton ``Input`` accessible via ``from pyluxel import Input``.
"""

import pygame

from pyluxel.debug import cprint

try:
    from pygame._sdl2.controller import Controller as _Controller
except ImportError:
    _Controller = None

# ── Event type constants (safe fallback) ──

_EV_PAD_DOWN = getattr(pygame, "CONTROLLERBUTTONDOWN", -1)
_EV_PAD_UP = getattr(pygame, "CONTROLLERBUTTONUP", -1)
_EV_PAD_AXIS = getattr(pygame, "CONTROLLERAXISMOTION", -1)
_EV_PAD_ADDED = getattr(pygame, "CONTROLLERDEVICEADDED", -1)
_EV_PAD_REMOVED = getattr(pygame, "CONTROLLERDEVICEREMOVED", -1)

_AXIS_MAX = 32767.0
_DEADZONE = 0.15
_TRIGGER_THRESHOLD = 0.3


# ── Trigger wrappers ──

class _MouseTrigger:
    __slots__ = ("button",)

    def __init__(self, button: int):
        self.button = button


class _PadTrigger:
    __slots__ = ("button",)

    def __init__(self, button: int):
        self.button = button


class _PadAxisTrigger:
    """Analog axis used as digital button (LT/RT)."""
    __slots__ = ("axis", "threshold")

    def __init__(self, axis: int, threshold: float = _TRIGGER_THRESHOLD):
        self.axis = axis
        self.threshold = threshold


class _StickAxis:
    __slots__ = ("axis",)

    def __init__(self, axis: int):
        self.axis = axis


# ── Convenience namespaces ──

class Mouse:
    LEFT = _MouseTrigger(1)
    MIDDLE = _MouseTrigger(2)
    RIGHT = _MouseTrigger(3)


class Pad:
    A = _PadTrigger(pygame.CONTROLLER_BUTTON_A)
    B = _PadTrigger(pygame.CONTROLLER_BUTTON_B)
    X = _PadTrigger(pygame.CONTROLLER_BUTTON_X)
    Y = _PadTrigger(pygame.CONTROLLER_BUTTON_Y)
    BACK = _PadTrigger(pygame.CONTROLLER_BUTTON_BACK)
    START = _PadTrigger(pygame.CONTROLLER_BUTTON_START)
    LB = _PadTrigger(pygame.CONTROLLER_BUTTON_LEFTSHOULDER)
    RB = _PadTrigger(pygame.CONTROLLER_BUTTON_RIGHTSHOULDER)
    LSTICK = _PadTrigger(pygame.CONTROLLER_BUTTON_LEFTSTICK)
    RSTICK = _PadTrigger(pygame.CONTROLLER_BUTTON_RIGHTSTICK)
    DPAD_UP = _PadTrigger(pygame.CONTROLLER_BUTTON_DPAD_UP)
    DPAD_DOWN = _PadTrigger(pygame.CONTROLLER_BUTTON_DPAD_DOWN)
    DPAD_LEFT = _PadTrigger(pygame.CONTROLLER_BUTTON_DPAD_LEFT)
    DPAD_RIGHT = _PadTrigger(pygame.CONTROLLER_BUTTON_DPAD_RIGHT)
    # Triggers as digital buttons (axis with threshold)
    LT = _PadAxisTrigger(pygame.CONTROLLER_AXIS_TRIGGERLEFT)
    RT = _PadAxisTrigger(pygame.CONTROLLER_AXIS_TRIGGERRIGHT)


class Stick:
    LEFT_X = _StickAxis(pygame.CONTROLLER_AXIS_LEFTX)
    LEFT_Y = _StickAxis(pygame.CONTROLLER_AXIS_LEFTY)
    RIGHT_X = _StickAxis(pygame.CONTROLLER_AXIS_RIGHTX)
    RIGHT_Y = _StickAxis(pygame.CONTROLLER_AXIS_RIGHTY)


# ── InputManager ──

class InputDevice:
    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    CONTROLLER = "controller"


class InputManager:
    """Centralized action-based input manager.

    Supports keyboard, mouse, and game controller.
    Query actions with ``pressed``, ``held``, ``released``, ``axis``.
    """

    def __init__(self):
        self._bindings: dict[str, list] = {}
        self._axis_bindings: dict[str, dict] = {}

        self._pressed: set[str] = set()
        self._held: set[str] = set()
        self._released: set[str] = set()
        self._axes: dict[str, float] = {}

        self._controller = None
        self._controller_probed = False

        self._last_device: str = InputDevice.KEYBOARD

    # ── Configuration ──

    def bind(self, action: str, *triggers):
        """Bind action to physical triggers.

        Each trigger is one of:
        - ``int``: pygame key constant (``pygame.K_SPACE``, etc.)
        - ``Mouse.*``: mouse button
        - ``Pad.*``: controller button or trigger
        """
        self._bindings[action] = list(triggers)

    def bind_axis(self, action: str, *, negative=None, positive=None, stick=None):
        """Bind an analog axis to digital triggers and/or analog stick.

        Digital triggers produce -1.0 (negative) or +1.0 (positive).
        Analog stick is -1.0 to 1.0 with deadzone.
        Final value = whichever has greater magnitude.
        """
        self._axis_bindings[action] = {
            "negative": negative or [],
            "positive": positive or [],
            "stick": stick,
        }
        self._axes[action] = 0.0

    def unbind(self, action: str) -> None:
        """Rimuove tutti i binding di un'azione."""
        self._bindings.pop(action, None)
        self._axis_bindings.pop(action, None)
        self._axes.pop(action, None)

    def is_bound(self, action: str) -> bool:
        """True se l'azione ha almeno un binding."""
        return action in self._bindings or action in self._axis_bindings

    def get_bindings(self, action: str) -> list:
        """Ritorna i trigger associati a un'azione, o lista vuota."""
        return list(self._bindings.get(action, []))

    def get_all_actions(self) -> list[str]:
        """Ritorna la lista di tutte le azioni registrate."""
        actions = set(self._bindings.keys())
        actions.update(self._axis_bindings.keys())
        return sorted(actions)

    def has_controller(self) -> bool:
        """True se un controller/gamepad e' connesso."""
        return self._controller is not None

    def get_controller_name(self) -> str | None:
        """Ritorna il nome del controller connesso, o None."""
        if self._controller:
            try:
                return self._controller.name
            except Exception:
                return "Unknown"
        return None

    # ── Per-frame update ──

    def update(self, events: list):
        """Process events and poll devices. Call once per frame."""
        prev_held = self._held
        self._pressed = set()
        self._released = set()
        self._held = set()

        # Probe controller already connected before first update
        if not self._controller_probed:
            self._controller_probed = True
            if not self._controller and _Controller:
                for i in range(pygame.joystick.get_count()):
                    self._open_controller(i)
                    if self._controller:
                        break

        # Controller hot-plug + last-device tracking
        for ev in events:
            if ev.type == _EV_PAD_ADDED:
                self._open_controller(ev.device_index)
            elif ev.type == _EV_PAD_REMOVED:
                self._close_controller()
            elif ev.type in (pygame.KEYDOWN, pygame.KEYUP):
                self._last_device = InputDevice.KEYBOARD
            elif ev.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                             pygame.MOUSEMOTION, pygame.MOUSEWHEEL):
                self._last_device = InputDevice.MOUSE
            elif ev.type in (_EV_PAD_DOWN, _EV_PAD_UP):
                self._last_device = InputDevice.CONTROLLER
            elif ev.type == _EV_PAD_AXIS:
                if abs(ev.value / _AXIS_MAX) > _DEADZONE:
                    self._last_device = InputDevice.CONTROLLER

        # Poll current device state
        keys = pygame.key.get_pressed()
        mouse = pygame.mouse.get_pressed()
        ctrl = self._controller

        # Digital actions
        for action, triggers in self._bindings.items():
            active = self._any_active(triggers, keys, mouse, ctrl)
            if active:
                self._held.add(action)
                if action not in prev_held:
                    self._pressed.add(action)
            elif action in prev_held:
                self._released.add(action)

        # Axes
        for action, binding in self._axis_bindings.items():
            neg = self._any_active(binding["negative"], keys, mouse, ctrl)
            pos = self._any_active(binding["positive"], keys, mouse, ctrl)
            digital = float(pos) - float(neg)

            analog = 0.0
            stick = binding["stick"]
            if stick and ctrl:
                raw = ctrl.get_axis(stick.axis) / _AXIS_MAX
                analog = raw if abs(raw) > _DEADZONE else 0.0

            self._axes[action] = digital if abs(digital) >= abs(analog) else analog

    # ── Queries ──

    def pressed(self, action: str) -> bool:
        """True on the frame the action was first pressed."""
        return action in self._pressed

    def held(self, action: str) -> bool:
        """True while the action is held down."""
        return action in self._held

    def released(self, action: str) -> bool:
        """True on the frame the action was released."""
        return action in self._released

    def axis(self, action: str) -> float:
        """Get axis value (-1.0 to 1.0)."""
        return self._axes.get(action, 0.0)

    @property
    def last_device(self) -> str:
        """Last input device used: ``InputDevice.KEYBOARD``, ``.MOUSE``, or ``.CONTROLLER``."""
        return self._last_device

    def is_using(self, device: str) -> bool:
        """Check if the last input came from the given device type."""
        return self._last_device == device

    # ── Internal ──

    def _any_active(self, triggers, keys, mouse, ctrl) -> bool:
        for t in triggers:
            if isinstance(t, int):
                if keys[t]:
                    return True
            elif isinstance(t, _PadAxisTrigger):
                if ctrl:
                    val = ctrl.get_axis(t.axis) / _AXIS_MAX
                    if val >= t.threshold:
                        return True
            elif isinstance(t, _MouseTrigger):
                if mouse[t.button - 1]:
                    return True
            elif isinstance(t, _PadTrigger):
                if ctrl and ctrl.get_button(t.button):
                    return True
        return False

    def _open_controller(self, device_index: int):
        if self._controller or not _Controller:
            return
        try:
            self._controller = _Controller(device_index)
        except pygame.error as e:
            cprint.warning("Controller open failed:", e)

    def _close_controller(self):
        if self._controller:
            try:
                self._controller.quit()
            except pygame.error as e:
                cprint.warning("Controller close failed:", e)
            self._controller = None
