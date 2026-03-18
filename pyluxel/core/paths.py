"""Path resolution e utility per dev mode, frozen builds e PAK."""

import sys
import os
from pathlib import Path
from typing import LiteralString


# ---- Dev vs frozen ----

def base_path() -> Path:
    """Root directory for bundled assets.

    - Dev: parent of the main script (project root)
    - PyInstaller: sys._MEIPASS (temp extraction dir)
    """
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(sys.argv[0]).resolve().parent


def exe_dir() -> str:
    """Directory dell'eseguibile / script principale (stringa)."""
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def user_data_dir(app_name: str) -> Path:
    """Writable directory for user data (settings, cache, saves).

    - Dev: same as base_path() (project root)
    - PyInstaller Win: %APPDATA%/app_name/
    - PyInstaller Mac: ~/Library/Application Support/app_name/
    - PyInstaller Linux: ~/.local/share/app_name/
    """
    if getattr(sys, 'frozen', False):
        if sys.platform == 'win32':
            base = Path(os.environ.get('APPDATA', str(Path.home())))
        elif sys.platform == 'darwin':
            base = Path.home() / 'Library' / 'Application Support'
        else:
            base = Path.home() / '.local' / 'share'
        d = base / app_name
        d.mkdir(parents=True, exist_ok=True)
        return d
    return base_path()


# ---- Path utilities per asset ----

def join(*parts: str) -> LiteralString | str | bytes:
    """Unisce segmenti di path (come os.path.join)."""
    return os.path.join(*parts)


def resolve_relative(base: str, relative: str) -> str:
    """Risolve un path relativo a partire da un file base.

    Esempio:
        resolve_relative("assets/maps/test.tmx", "../tileset/Castle.tsx")
        -> "assets/tileset/Castle.tsx"
    """
    base_dir = os.path.dirname(base)
    return os.path.normpath(os.path.join(base_dir, relative))


def filename(path: str) -> str:
    """Estrae il nome del file (con estensione) da un path."""
    return os.path.basename(path)


def extension(path: str) -> str:
    """Estrae l'estensione (con punto, es. '.png')."""
    return os.path.splitext(path)[1]


def exists(path: str) -> bool:
    """True se il file esiste su disco."""
    return os.path.exists(path)
