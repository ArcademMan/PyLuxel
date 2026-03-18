"""python -m pyluxel -- CLI entry point."""

from __future__ import annotations

import sys


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print("PyLuxel CLI")
        print()
        print("Comandi disponibili:")
        print("  pyluxel pak <directory>   Impacchetta asset in un file .pak")
        print()
        print("Usa 'pyluxel <comando> -h' per dettagli.")
        return

    command = args[0]

    if command == "pak":
        from pyluxel.cli.pak_cmd import run
        run(args[1:])
    else:
        print(f"Comando sconosciuto: '{command}'", file=sys.stderr)
        print("Usa 'pyluxel -h' per la lista dei comandi.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
