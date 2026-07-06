from functools import lru_cache

import networkx as nx

from catalog.crawler import crawl
from catalog.fk_inference import infer_foreign_keys
from catalog.join_graph import build_join_graph
from db.schema_spec import TABLES as SCHEMA_TABLES


@lru_cache(maxsize=1)
def _graph():
    crawled = crawl()
    modules = {t: SCHEMA_TABLES[t]["module"] for t in crawled if t in SCHEMA_TABLES}
    inferred = infer_foreign_keys(crawled)
    return build_join_graph(crawled, inferred, modules)


def test_declared_edges_full_confidence_inferred_edges_lower():
    G = _graph()
    declared = [d for _, _, d in G.edges(data=True) if d["declared"]]
    inferred = [d for _, _, d in G.edges(data=True) if not d["declared"]]
    assert declared and inferred
    assert all(d["confidence"] == 1.0 for d in declared)
    assert all(d["confidence"] < 1.0 for d in inferred)


def test_path_exists_between_ord_dtl_2_and_item_mst():
    G = _graph()
    assert nx.has_path(G, "ord_dtl_2", "item_mst")


def test_disjoint_department_employee_paths_not_collapsed():
    G = _graph()
    edge_data = G.get_edge_data("department", "employee")
    assert edge_data is not None
    assert len(edge_data) >= 2, "manages/works_in edges collapsed into one"
    labels = {d["label"] for d in edge_data.values()}
    assert {"manages", "works_in"} <= labels
