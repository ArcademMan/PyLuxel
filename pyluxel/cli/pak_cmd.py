"""pyluxel pak -- Impacchetta una cartella di asset in un file .pak.

Uso:
    pyluxel pak assets/
    pyluxel pak assets/ -o data.pak
    pyluxel pak assets/ --key "MiaChiaveCustom"
    pyluxel pak assets/ --exclude cache --exclude temp
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import zipfile

# Stessa chiave di default usata in pyluxel.core.pak
_DEFAULT_KEY = b"V0idS0uls_2026!"


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    """XOR ciclico su bytes."""
    key_len = len(key)
    return bytes(b ^ key[i % key_len] for i, b in enumerate(data))


def run(args: list[str] | None = None) -> None:
    """Entry point per il comando pak."""
    parser = argparse.ArgumentParser(
        prog="pyluxel pak",
        description="Impacchetta una cartella di asset in un file .pak offuscato.",
    )
    parser.add_argument(
        "directory",
        help="Cartella da impacchettare (es. assets/)",
    )
    parser.add_argument(
        "-o", "--output",
        default="data.pak",
        help="File di output (default: data.pak)",
    )
    parser.add_argument(
        "--key",
        default=None,
        help="Chiave XOR personalizzata (default: chiave built-in)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Nomi di directory da escludere (ripetibile, es. --exclude cache --exclude temp)",
    )

    parsed = parser.parse_args(args)

    directory = parsed.directory.rstrip("/\\")
    output = parsed.output
    key = parsed.key.encode("utf-8") if parsed.key else _DEFAULT_KEY
    exclude = set(parsed.exclude)

    if not os.path.isdir(directory):
        print(f"Errore: '{directory}' non e' una directory.", file=sys.stderr)
        sys.exit(1)

    # Crea zip in memoria
    buf = io.BytesIO()
    count = 0

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(directory):
            # Escludi directory non volute
            dirs[:] = [d for d in dirs if d not in exclude]

            for filename in files:
                filepath = os.path.join(root, filename)
                # Nel zip usa forward slash
                arcname = filepath.replace("\\", "/")
                zf.write(filepath, arcname)
                count += 1

    # XOR e salva
    zip_bytes = buf.getvalue()
    pak_bytes = _xor_bytes(zip_bytes, key)

    with open(output, "wb") as f:
        f.write(pak_bytes)

    size_mb = len(pak_bytes) / (1024 * 1024)
    print(f"Creato {output}: {count} file, {size_mb:.1f} MB")
