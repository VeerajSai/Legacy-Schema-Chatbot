"""Convenience script: regenerate everything from scratch.
Run with: python scripts/build_all.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # allow `python scripts/build_all.py` directly

from db.build import build as build_db  # noqa: E402


def main() -> None:
    print("[1/3] Building data/legacy.db ...", flush=True)
    build_db()

    print("[2/3] Building catalog (table cards + join graph) ...", flush=True)
    subprocess.run([sys.executable, "-m", "catalog.build_catalog"], check=True)

    print("[3/3] Resolving golden set against the DB ...", flush=True)
    subprocess.run([sys.executable, "-m", "eval.build_golden_set"], check=True)

    print("Done.")


if __name__ == "__main__":
    main()
