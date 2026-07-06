"""Post-processing after seed_database(): deterministically engineers the
specific stress cases the eval/tests rely on, rather than hoping random data
happens to produce them.
"""
from __future__ import annotations

import random
import sqlite3

from db.schema_spec import MIXED_CASE_TABLES


def _force_disjoint_path(conn: sqlite3.Connection) -> None:
    """Employee 1 'manages' department 1 (via department.manager_emp_id) but
    'works_in' department 2 (via emp_dept_assign) — the doc's exact trap: two
    real, declared, semantically different paths between employee and
    department that must NOT collapse into one in graph_expand.py."""
    conn.execute("UPDATE department SET manager_emp_id = 1 WHERE dept_id = 1")
    existing = conn.execute(
        "SELECT assign_id FROM emp_dept_assign WHERE emp_id = 1"
    ).fetchone()
    if existing:
        conn.execute("UPDATE emp_dept_assign SET dept_id = 2 WHERE assign_id = ?", (existing[0],))
    else:
        next_id = conn.execute("SELECT COALESCE(MAX(assign_id), 0) + 1 FROM emp_dept_assign").fetchone()[0]
        conn.execute(
            "INSERT INTO emp_dept_assign (assign_id, emp_id, dept_id) VALUES (?, 1, 2)", (next_id,)
        )


def _mix_categorical_case(conn: sqlite3.Connection, seed: int) -> None:
    """~10% of rows in the flagged legacy tables get their categorical value
    lowercased ('shipped' vs stored 'SHIPPED') — doc's #1 silent failure,
    reproducible for the empty-result repair-loop demo."""
    rng = random.Random(seed)
    for table, col in MIXED_CASE_TABLES.items():
        pk_col = conn.execute(f"PRAGMA table_info({table})").fetchall()
        pk_name = next(r[1] for r in pk_col if r[5] == 1)  # PRAGMA table_info: row[5]=pk flag
        ids = [r[0] for r in conn.execute(f"SELECT {pk_name} FROM {table}").fetchall()]
        sample = rng.sample(ids, k=max(1, len(ids) // 10))
        for row_id in sample:
            current = conn.execute(
                f"SELECT {col} FROM {table} WHERE {pk_name} = ?", (row_id,)
            ).fetchone()[0]
            conn.execute(
                f"UPDATE {table} SET {col} = ? WHERE {pk_name} = ?", (current.lower(), row_id)
            )


def apply_bridge_scenarios(conn: sqlite3.Connection, seed: int = 42) -> None:
    _force_disjoint_path(conn)
    _mix_categorical_case(conn, seed)
    conn.commit()
