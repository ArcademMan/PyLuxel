"""Colored console printer for pyluxel — singleton, usable everywhere."""

import inspect
import os
import sys
from datetime import datetime

# ANSI color codes
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"

_COLORS = {
    "info":    "\033[36m",       # cyan
    "warning": "\033[33m",       # yellow
    "error":   "\033[91m",       # bright red
    "ok":      "\033[32m",       # green
    "debug":   "\033[90m",       # gray
}

_LABELS = {
    "info":    "INFO ",
    "warning": "WARN ",
    "error":   "ERROR",
    "ok":      "OK   ",
    "debug":   "DEBUG",
}

# Enable ANSI on Windows 10+
if sys.platform == "win32":
    os.system("")


class _CPrint:
    """Colored console logger with automatic caller info.

    Usage:
        from pyluxel import cprint
        cprint.info("Renderer initialized")
        cprint.warning("GPU release failed:", err)
        cprint.error("Shader compilation failed")
        cprint.ok("Map loaded successfully")
        cprint.debug("Frame time:", dt)

    Each message shows: [HH:MM:SS] LEVEL file.py:line >> message
    """

    def __init__(self):
        self.enabled = True

    def _log(self, level: str, *args, stack_offset: int = 2):
        if not self.enabled:
            return

        # Caller info
        frame = inspect.stack()[stack_offset]
        filename = os.path.basename(frame.filename)
        lineno = frame.lineno

        # Timestamp
        now = datetime.now().strftime("%H:%M:%S")

        # Build message
        msg = " ".join(str(a) for a in args)
        color = _COLORS.get(level, "")
        label = _LABELS.get(level, level.upper())

        print(
            f"{_DIM}[{now}]{_RESET} "
            f"{color}{_BOLD}{label}{_RESET} "
            f"{_DIM}{filename}:{lineno}{_RESET} "
            f"{color}>> {msg}{_RESET}"
        )

    def info(self, *args):
        self._log("info", *args)

    def warning(self, *args):
        self._log("warning", *args)

    def error(self, *args):
        self._log("error", *args)

    def ok(self, *args):
        self._log("ok", *args)

    def debug(self, *args):
        self._log("debug", *args)
