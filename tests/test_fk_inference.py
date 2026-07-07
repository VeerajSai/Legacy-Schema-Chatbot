import sqlite3
from functools import lru_cache

from catalog import fk_inference
from catalog.crawler import crawl
from catalog.fk_inference import infer_foreign_keys


@lru_cache(maxsize=1)
def _edges():
    return tuple(infer_foreign_keys(crawl()))


def test_recovers_known_undeclared_fks():
    found = {(e.left_table, e.left_col, e.right_table, e.right_col) for e in _edges()}
    expected = {
        ("ord_dtl_2", "item_id", "item_mst", "item_id"),
        ("invoice_hdr", "cust_id", "cust_mst", "cust_id"),
        ("po_hdr", "buyer_emp_id", "employee", "emp_id"),
    }
    assert expected <= found


def test_inferred_edges_are_undeclared_and_below_full_confidence():
    edges = _edges()
    assert edges
    assert all(not e.declared for e in edges)
    assert all(e.confidence < 1.0 for e in edges)


def test_pk_name_collision_checks_every_candidate_table(monkeypatch):
    """Two synthetic tables share the single-column PK name 'code_id' (like
    hist_id/map_id colliding for real in this schema). The candidate column's
    values only satisfy the inclusion-dependency check against tbl_first --
    a last-write-wins {pk_name: table} map would silently keep whichever of
    tbl_first/tbl_second got crawled last and could drop the real match
    entirely instead of testing both."""
    crawled = {
        "tbl_first": {
            "columns": [{"name": "code_id", "dtype": "INTEGER", "pk": True, "notnull": True}],
            "fks": [], "row_count": 3,
        },
        "tbl_second": {
            "columns": [{"name": "code_id", "dtype": "INTEGER", "pk": True, "notnull": True}],
            "fks": [], "row_count": 3,
        },
        "candidate_tbl": {
            "columns": [
                {"name": "id", "dtype": "INTEGER", "pk": True, "notnull": True},
                {"name": "code_id", "dtype": "INTEGER", "pk": False, "notnull": False},
            ],
            "fks": [], "row_count": 2,
        },
    }
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("CREATE TABLE tbl_first (code_id INTEGER)")
    cur.executemany("INSERT INTO tbl_first VALUES (?)", [(1,), (2,), (3,)])
    cur.execute("CREATE TABLE tbl_second (code_id INTEGER)")
    cur.executemany("INSERT INTO tbl_second VALUES (?)", [(5,), (6,), (7,)])
    cur.execute("CREATE TABLE candidate_tbl (id INTEGER, code_id INTEGER)")
    cur.executemany("INSERT INTO candidate_tbl VALUES (?, ?)", [(1, 1), (2, 2)])
    conn.commit()

    monkeypatch.setattr(fk_inference, "get_connection", lambda read_only=True: conn)

    edges = fk_inference.infer_foreign_keys(crawled)
    matches = {(e.left_table, e.left_col, e.right_table, e.right_col) for e in edges}

    # real match: candidate_tbl.code_id values {1,2} subset of tbl_first {1,2,3}
    assert ("candidate_tbl", "code_id", "tbl_first", "code_id") in matches
    # decoy sharing the same PK name must be tried and correctly rejected
    # ({1,2} not subset of tbl_second's {5,6,7}), not silently skipped
    assert ("candidate_tbl", "code_id", "tbl_second", "code_id") not in matches
