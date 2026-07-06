import sqlite3
from pathlib import Path

from db.bridge_scenarios import apply_bridge_scenarios
from db.generate_data import seed_database
from db.generate_schema import create_schema
from db.schema_spec import TABLES


def _build(tmp_path: Path, name: str = "test_legacy.db") -> sqlite3.Connection:
    db_path = tmp_path / name
    conn = sqlite3.connect(db_path)
    create_schema(conn)
    seed_database(conn, seed=42)
    apply_bridge_scenarios(conn, seed=42)
    return conn


def test_table_count_in_range(tmp_path):
    assert 60 <= len(TABLES) <= 80


def test_no_empty_tables(tmp_path):
    conn = _build(tmp_path)
    for table in TABLES:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert count > 0, f"{table} is empty"


def test_has_undeclared_fk_column(tmp_path):
    conn = _build(tmp_path)
    # ord_dtl_2.item_id is FK-shaped (references item_mst.item_id) but declared=False
    fk_list = conn.execute("PRAGMA foreign_key_list(ord_dtl_2)").fetchall()
    fk_cols = {row[3] for row in fk_list}  # row[3] = "from" column
    assert "item_id" not in fk_cols
    assert "ord_id" in fk_cols  # this one IS declared


def test_disjoint_path_scenario(tmp_path):
    conn = _build(tmp_path)
    manager_dept = conn.execute("SELECT dept_id FROM department WHERE manager_emp_id = 1").fetchone()
    assign_dept = conn.execute("SELECT dept_id FROM emp_dept_assign WHERE emp_id = 1").fetchone()
    assert manager_dept is not None and assign_dept is not None
    assert manager_dept[0] != assign_dept[0]


def test_reproducible_with_same_seed(tmp_path):
    conn_a = _build(tmp_path, "a.db")
    row_a = conn_a.execute("SELECT cust_nm FROM cust_mst WHERE cust_id = 1").fetchone()[0]
    conn_b = _build(tmp_path, "b.db")
    row_b = conn_b.execute("SELECT cust_nm FROM cust_mst WHERE cust_id = 1").fetchone()[0]
    assert row_a == row_b
