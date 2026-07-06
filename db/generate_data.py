"""Seeds data/legacy.db from db/schema_spec.py. Deterministic given a seed:
tables are filled in FK-dependency topological order (declared or undeclared
FKs both count, so referential integrity holds even for undeclared ones),
and every FK column samples from the referenced table's already-generated
primary keys."""
from __future__ import annotations

import random
import sqlite3

from faker import Faker

from db.schema_spec import TABLES

_AMT_HINTS = ("amt", "price", "cost", "rate", "pct", "wt", "target")
_INT_HINTS = ("qty", "score", "count")


def _topo_order() -> list[str]:
    deps = {t: set() for t in TABLES}
    for t, spec in TABLES.items():
        for c in spec["columns"]:
            if c["fk"]:
                ref_table = c["fk"][0]
                if ref_table != t:
                    deps[t].add(ref_table)
    order: list[str] = []
    seen: set[str] = set()

    def visit(t: str, stack: set[str]) -> None:
        if t in seen:
            return
        if t in stack:
            raise ValueError(f"cycle detected in schema_spec FK graph at {t}")
        stack = stack | {t}
        for dep in deps[t]:
            visit(dep, stack)
        seen.add(t)
        order.append(t)

    for t in TABLES:
        visit(t, set())
    return order


def _fake_text(table: str, name: str, faker: Faker) -> str:
    if "email" in name:
        return faker.unique.email()
    if name.endswith("_nm"):
        if "cust" in table or "vendor" in table or "account" in table:
            return faker.company()
        if table == "employee" or "contact" in table:
            return faker.name()
        if "item" in table:
            return faker.word().capitalize() + " " + faker.word().capitalize()
        return faker.catch_phrase()
    if name in ("addr_line",):
        return faker.street_address()
    if name in ("city",):
        return faker.city()
    if name in ("iban",):
        return faker.iban()
    if name in ("aisle", "bin"):
        return faker.bothify(text="??-##")
    if name in ("file_nm",):
        return faker.file_name()
    if name in ("action",):
        return random.choice(["VIEW", "UPDATE", "EXPORT", "LOGIN"])
    if name in ("entity_type",):
        return random.choice(["order", "invoice", "contract", "ticket"])
    return faker.word()


def _gen_value(table: str, col: dict, fk_pools: dict[str, list], faker: Faker):
    name, dtype = col["name"], col["dtype"]
    if col["fk"]:
        ref_table = col["fk"][0]
        return random.choice(fk_pools[ref_table])
    if col["enum"]:
        return random.choice(col["enum"])
    if name.endswith("_dt"):
        return faker.date_between(start_date="-3y", end_date="today").isoformat()
    if dtype == "REAL":
        if any(h in name for h in _AMT_HINTS):
            return round(random.uniform(5, 5000), 2)
        return round(random.uniform(0, 100), 2)
    if dtype == "INTEGER":
        if any(h in name for h in _INT_HINTS):
            return random.randint(1, 200)
        return random.randint(1, 1000)
    return _fake_text(table, name, faker)


def _resolve_row_count(spec: dict, row_counts: dict[str, int]) -> int:
    rows = spec["rows"]
    if isinstance(rows, int):
        return rows
    _, parent, lo, hi = rows
    return max(1, round(row_counts[parent] * random.uniform(lo, hi)))


def seed_database(conn: sqlite3.Connection, seed: int = 42) -> None:
    random.seed(seed)
    Faker.seed(seed)
    faker = Faker()

    fk_pools: dict[str, list] = {}
    row_counts: dict[str, int] = {}

    for table in _topo_order():
        spec = TABLES[table]
        cols = spec["columns"]
        col_names = [c["name"] for c in cols]

        if "fixed_rows" in spec:
            rows = spec["fixed_rows"]
        else:
            n = _resolve_row_count(spec, row_counts)
            rows = []
            for i in range(n):
                row = {}
                for c in cols:
                    if c["pk"] and c["dtype"] == "INTEGER":
                        row[c["name"]] = i + 1
                    else:
                        row[c["name"]] = _gen_value(table, c, fk_pools, faker)
                rows.append(row)

        placeholders = ", ".join(["?"] * len(col_names))
        sql = f'INSERT INTO {table} ({", ".join(col_names)}) VALUES ({placeholders})'
        conn.executemany(sql, [[r[c] for c in col_names] for r in rows])

        pk_col = next((c["name"] for c in cols if c["pk"]), None)
        fk_pools[table] = [r[pk_col] for r in rows] if pk_col else []
        row_counts[table] = len(rows)

    conn.commit()
