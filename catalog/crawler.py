"""Introspects the live DB (data/legacy.db) via sqlite_master + PRAGMA. This is
the only module allowed to talk to sqlite_master/PRAGMA directly — everything
downstream (fk_inference, enumerations, join_graph, describe) works off the
dict this returns, not off db/schema_spec.py.
"""
from __future__ import annotations

from contracts.db import get_connection


def crawl() -> dict[str, dict]:
    """Returns {table: {"columns": [...], "fks": [...], "row_count": int}}.

    columns: [{"name", "dtype", "pk", "notnull"}, ...] from PRAGMA table_info.
    fks: [{"column", "ref_table", "ref_column"}, ...] from PRAGMA foreign_key_list
    (i.e. only FKs that were declared as real SQLite constraints).
    """
    conn = get_connection(read_only=True)
    try:
        cur = conn.cursor()
        tables = [
            r["name"] for r in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
        crawled: dict[str, dict] = {}
        for table in tables:
            columns = [
                {
                    "name": row["name"],
                    "dtype": row["type"] or "TEXT",
                    "pk": bool(row["pk"]),
                    "notnull": bool(row["notnull"]),
                }
                for row in cur.execute(f"PRAGMA table_info({table})").fetchall()
            ]
            fks = [
                {
                    "column": row["from"],
                    "ref_table": row["table"],
                    "ref_column": row["to"],
                }
                for row in cur.execute(f"PRAGMA foreign_key_list({table})").fetchall()
            ]
            row_count = cur.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
            crawled[table] = {"columns": columns, "fks": fks, "row_count": row_count}
        return crawled
    finally:
        conn.close()
