"""Populates ColumnCard.distinct_values for low-cardinality columns by
querying the live DB (per doc: enumerating small code/status columns is what
lets stage-7 SQL gen use exact literal values instead of guessing casing)."""
from __future__ import annotations

from config.settings import LOW_CARDINALITY_THRESHOLD
from contracts.db import get_connection


def enumerate_low_cardinality(crawled: dict) -> dict[str, dict[str, list[str]]]:
    """{table: {column: [distinct values]}} for columns with 0 < distinct count < threshold."""
    conn = get_connection(read_only=True)
    result: dict[str, dict[str, list[str]]] = {}
    try:
        cur = conn.cursor()
        for table, info in crawled.items():
            cols: dict[str, list[str]] = {}
            for c in info["columns"]:
                col = c["name"]
                count = cur.execute(f"SELECT COUNT(DISTINCT {col}) AS c FROM {table}").fetchone()["c"]
                if 0 < count < LOW_CARDINALITY_THRESHOLD:
                    rows = cur.execute(
                        f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL ORDER BY {col}"
                    ).fetchall()
                    cols[col] = [str(r[0]) for r in rows]
            if cols:
                result[table] = cols
    finally:
        conn.close()
    return result
