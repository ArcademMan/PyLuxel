"""pyluxel.core.pak -- Sistema PAK per protezione asset.

In dev mode (nessun pak caricato), asset_open() e' un semplice wrapper
attorno a open(). Quando un .pak e' caricato (build Nuitka), i file
vengono letti dal pak in memoria.

Formato .pak: zip standard con XOR ciclico applicato all'intero file.
"""

from __future__ import annotations

import io
import os
import zipfile
from typing import BinaryIO

from pyluxel.debug import cprint

# Chiave XOR di default (puo' essere sovrascritta in init_pak)
_DEFAULT_KEY = b"V0idS0uls_2026!"


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    """XOR ciclico su bytes."""
    if not key:
        return data
    key_len = len(key)
    return bytes(b ^ key[i % key_len] for i, b in enumerate(data))


def _normalize_path(path: str) -> str:
    """Normalizza un path per il lookup nel pak.

    Converte backslash in forward slash, rimuove ./ prefisso,
    e normalizza i path relativi (../).
    """
    p = path.replace("\\", "/")
    # Rimuovi ./ prefisso
    while p.startswith("./"):
        p = p[2:]
    # Normalizza segmenti (gestisce ../)
    parts = []
    for seg in p.split("/"):
        if seg == "..":
            if parts:
                parts.pop()
        elif seg and seg != ".":
            parts.append(seg)
    return "/".join(parts)


class PakFile:
    """Archivio PAK: zip offuscato con XOR."""

    def __init__(self, pak_path: str, key: bytes = _DEFAULT_KEY):
        with open(pak_path, "rb") as f:
            raw = f.read()

        decrypted = _xor_bytes(raw, key)
        self._zip = zipfile.ZipFile(io.BytesIO(decrypted), "r")
        self._names: set[str] = set(self._zip.namelist())
        cprint.ok(f"PAK: caricato {pak_path} ({len(self._names)} file)")

    def _resolve(self, name: str) -> str | None:
        """Risolve un path alla chiave nel pak.

        Prova prima il match diretto, poi fallback per path assoluti:
        se il path normalizzato finisce con una chiave del pak, usa quella.
        """
        key = _normalize_path(name)
        if key in self._names:
            return key
        # Fallback: path assoluto → cerca suffisso corrispondente
        for pak_name in self._names:
            if key.endswith("/" + pak_name):
                return pak_name
        return None

    def open(self, name: str) -> io.BytesIO:
        """Restituisce il contenuto di un file come BytesIO."""
        key = self._resolve(name)
        if key is None:
            raise FileNotFoundError(f"PAK: file non trovato: {name}")
        data = self._zip.read(key)
        return io.BytesIO(data)

    def exists(self, name: str) -> bool:
        """True se il file esiste nel pak."""
        return self._resolve(name) is not None

    def list(self) -> list[str]:
        """Lista di tutti i file nel pak."""
        return sorted(self._names)


# --- Stato globale ---

_pak: PakFile | None = None


def init_pak(pak_path: str, key: bytes = _DEFAULT_KEY) -> None:
    """Carica un file .pak come sorgente globale degli asset."""
    global _pak
    _pak = PakFile(pak_path, key)


def has_pak() -> bool:
    """True se un pak e' attivo."""
    return _pak is not None


def asset_open(path: str) -> BinaryIO:
    """Apre un asset: dal pak se attivo, altrimenti da disco.

    Restituisce un file-like object in modalita' binaria (BytesIO o file).
    """
    if _pak is not None and _pak.exists(path):
        return _pak.open(path)
    return open(path, "rb")


def asset_exists(path: str) -> bool:
    """True se l'asset esiste (nel pak o su disco)."""
    if _pak is not None:
        return _pak.exists(path)
    return os.path.exists(path)
