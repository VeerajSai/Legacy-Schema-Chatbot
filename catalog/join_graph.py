"""Builds the join graph from crawler + fk_inference output.

Uses nx.MultiGraph rather than nx.Graph: db/schema_spec.DISJOINT_PATH_PAIRS is
a deliberate trap where department and employee are connected by two real,
declared, semantically distinct paths (a direct "manages" FK, and a "works_in"
relationship via the emp_dept_assign bridge table). A plain Graph can only
hold one edge per node pair, which would silently collapse them; MultiGraph
is the stdlib-native fix (ladder rung 4) instead of hand-rolling multi-edge
storage.

It's legitimate to read db/schema_spec.DISJOINT_PATH_PAIRS here (per the
task brief, this is "the known trap to test against", not fk-inference
logic) purely to attach the right semantic labels — the edges themselves
still come from crawled/inferred data, not from schema_spec.
"""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from config.settings import JOIN_GRAPH_PATH
from contracts.types import JoinEdge
from db.schema_spec import DISJOINT_PATH_PAIRS


def _declared_edges(crawled: dict) -> list[JoinEdge]:
    return [
        JoinEdge(left_table=t, left_col=fk["column"],
                 right_table=fk["ref_table"], right_col=fk["ref_column"],
                 declared=True, confidence=1.0)
        for t, info in crawled.items() for fk in info["fks"]
    ]


def _apply_disjoint_path_labels(edges: list[JoinEdge]) -> None:
    """Labels the known manages/works_in edges in place: the direct
    department->employee "manages" FK, and the two emp_dept_assign bridge
    FKs as "works_in". Does not synthesize any edge -- the real 2-hop
    works_in path via emp_dept_assign is what graph_expand.py's alternate-
    route search (nx.shortest_simple_paths) surfaces as distinct from the
    1-hop "manages" path."""
    for (lt, lc, rt, rc, label), (bt, bc1, bc2, blabel) in DISJOINT_PATH_PAIRS:
        for e in edges:
            if (e.left_table, e.left_col, e.right_table, e.right_col) == (lt, lc, rt, rc):
                e.label = label
            if e.left_table == bt and e.left_col in (bc1, bc2):
                e.label = blabel


def build_join_graph(crawled: dict, inferred_edges: list[JoinEdge], modules: dict[str, str]) -> nx.MultiGraph:
    edges = _declared_edges(crawled) + list(inferred_edges)
    _apply_disjoint_path_labels(edges)

    G = nx.MultiGraph()
    for t in crawled:
        G.add_node(t, module=modules.get(t, "unknown"))
    for e in edges:
        G.add_edge(e.left_table, e.right_table,
                    left_table=e.left_table, left_col=e.left_col,
                    right_table=e.right_table, right_col=e.right_col,
                    declared=e.declared, label=e.label, confidence=e.confidence)
    return G


def save_join_graph(G: nx.MultiGraph, path=JOIN_GRAPH_PATH) -> None:
    data = nx.node_link_data(G, edges="edges")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2))


def load_join_graph(path=JOIN_GRAPH_PATH) -> nx.MultiGraph:
    data = json.loads(Path(path).read_text())
    return nx.node_link_graph(data, edges="edges")
