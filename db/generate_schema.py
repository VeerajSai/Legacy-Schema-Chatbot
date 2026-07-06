"""Turns db/schema_spec.py into CREATE TABLE DDL and executes it against a
fresh sqlite file. Declared FKs get a real FOREIGN KEY constraint; undeclared
ones are just a plain column (that's the whole point — legacy DBs often lack
declared constraints, and catalog/fk_inference.py has to recover them)."""
from __future__ import annotations

import sqlite3

from db.schema_spec import TABLES


def _column_ddl(col: dict) -> str:
    if col["pk"] and col["dtype"] == "INTEGER":
        return f'{col["name"]} INTEGER PRIMARY KEY'
    if col["pk"]:
        return f'{col["name"]} {col["dtype"]} PRIMARY KEY'
    suffix = "" if col["nullable"] else " NOT NULL"
    return f'{col["name"]} {col["dtype"]}{suffix}'


def create_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    for table, spec in TABLES.items():
        cols_ddl = [_column_ddl(c) for c in spec["columns"]]
        fk_ddl = []
        for c in spec["columns"]:
            if c["fk"] and c["fk"][2]:  # declared only
                ref_table, ref_col, _declared = c["fk"]
                fk_ddl.append(f'FOREIGN KEY ({c["name"]}) REFERENCES {ref_table}({ref_col})')
        ddl = f'CREATE TABLE {table} (\n  ' + ",\n  ".join(cols_ddl + fk_ddl) + "\n)"
        conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.execute(ddl)
    conn.commit()
