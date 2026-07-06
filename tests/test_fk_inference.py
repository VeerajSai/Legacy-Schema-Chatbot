from functools import lru_cache

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
