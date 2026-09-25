"""Windows entry point for the self-contained desktop application."""
import os
import sys

# A PyInstaller --windowed executable has no console streams.  The backend logs
# only informational startup messages, so provide a harmless sink for them.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

from backend import main


if __name__ == "__main__":
    raise SystemExit(main())
