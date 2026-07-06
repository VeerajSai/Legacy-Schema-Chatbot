"""CLI: python -m db.build --seed 42
Builds data/legacy.db from scratch: schema, seed data, then engineered stress cases."""
from __future__ import annotations

import argparse
import sqlite3

from config.settings import DB_PATH, DB_SEED
from db.bridge_scenarios import apply_bridge_scenarios
from db.generate_data import seed_database
from db.generate_schema import create_schema


def build(seed: int = DB_SEED, db_path=DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    try:
        create_schema(conn)
        seed_database(conn, seed=seed)
        apply_bridge_scenarios(conn, seed=seed)
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=DB_SEED)
    args = parser.parse_args()
    build(seed=args.seed)
    print(f"Built {DB_PATH} with seed={args.seed}")
