"""SQLite connection helper. Read-only mode for the online query plane, per
doc section 8 (execution runs against a read-only connection)."""
from __future__ import annotations

import sqlite3

from config.settings import DB_PATH


def get_connection(read_only: bool = True) -> sqlite3.Connection:
    if read_only:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
