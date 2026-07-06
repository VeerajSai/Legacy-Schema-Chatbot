"""Stage 4 (doc section 4): graph expansion. Pairwise shortest paths + union
over the retrieved candidate tables (a full Steiner-tree solver is unwarranted
at ~74 tables, per the design doc itself), plus an explicit check for the
doc's disjoint-path trap: two real, differently-labeled FKs between the same
two tables (e.g. department<->employee via "manages" vs "works_in")."""
from __future__ import annotations

import itertools

import networkx as nx

from contracts.types import GraphExpansionResult, JoinEdge, RetrievalResult, TableCard


def _edge_weight(attrs: dict) -> float:
    """Declared edges are cheaper than inferred ones; low profiling confidence
    on an inferred edge costs a little extra."""
    declared = attrs.get("declared", False)
    confidence = attrs.get("confidence", 1.0)
    return (1.0 if declared else 2.0) + (1.0 - confidence)


def _is_multi_edge_data(data: dict) -> bool:
    """join_graph is an nx.MultiGraph (see catalog/join_graph.py) so that the
    department<->employee 'manages' vs 'works_in' trap can hold two parallel
    edges instead of collapsing to one. get_edge_data on a MultiGraph returns
    {edge_key: attrs, ...} rather than a flat attrs dict; detect which shape
    we were handed so the same helpers work for either graph type."""
    return bool(data) and all(isinstance(v, dict) for v in data.values())


def _edge_variants(graph: nx.Graph, u: str, v: str) -> list[dict]:
    data = graph.get_edge_data(u, v)
    if data is None:
        return []
    return list(data.values()) if _is_multi_edge_data(data) else [data]


def _weight(u: str, v: str, data: dict) -> float:
    """Signature networkx calls directly during shortest_path; `data` has the
    same u/v-get_edge_data shape as `_edge_variants` handles above."""
    if _is_multi_edge_data(data):
        return min(_edge_weight(attrs) for attrs in data.values())
    return _edge_weight(data)


def _path_cost(graph: nx.Graph, path: list[str]) -> float:
    return sum(_weight(a, b, graph.get_edge_data(a, b)) for a, b in zip(path, path[1:]))


def _path_labels(graph: nx.Graph, path: list[str]) -> tuple[str, ...]:
    labels = []
    for a, b in zip(path, path[1:]):
        variants = _edge_variants(graph, a, b)
        best = min(variants, key=_edge_weight)
        labels.append(best.get("label", ""))
    return tuple(sorted(labels))


def _simple_view(graph: nx.Graph) -> nx.Graph:
    """nx.shortest_simple_paths has no multigraph support at all. It's only
    used here to search for alternate NODE ROUTES (parallel edges on the same
    hop are already caught directly in expand_with_graph), so a plain Graph
    collapsed to each pair's cheapest edge is a faithful stand-in for that
    specific search."""
    if not graph.is_multigraph():
        return graph
    simple = nx.Graph()
    simple.add_nodes_from(graph.nodes(data=True))
    for u, v in graph.edges():
        if simple.has_edge(u, v):
            continue
        best = min(_edge_variants(graph, u, v), key=_edge_weight)
        simple.add_edge(u, v, **best)
    return simple


def _edge_to_join_edge(data: dict) -> JoinEdge:
    return JoinEdge(
        left_table=data["left_table"],
        left_col=data["left_col"],
        right_table=data["right_table"],
        right_col=data["right_col"],
        declared=data.get("declared", False),
        label=data.get("label", ""),
        confidence=data.get("confidence", 1.0),
    )


def expand_with_graph(
    retrieval: RetrievalResult,
    join_graph: nx.Graph,
    table_cards_by_name: dict[str, TableCard],
) -> GraphExpansionResult:
    candidates = [t for t in retrieval.candidate_tables if t in join_graph]
    all_nodes: set[str] = set(candidates)
    primary_edges: dict[frozenset, JoinEdge] = {}
    ambiguous: list[list[JoinEdge]] = []
    seen_ambiguous_pairs: set[frozenset] = set()
    simple_graph = _simple_view(join_graph)

    for u, v in itertools.combinations(candidates, 2):
        if not nx.has_path(join_graph, u, v):
            continue

        primary = nx.shortest_path(join_graph, u, v, weight=_weight)
        all_nodes.update(primary)
        for a, b in zip(primary, primary[1:]):
            hop_variants = _edge_variants(join_graph, a, b)
            best = min(hop_variants, key=_edge_weight)
            primary_edges[frozenset((a, b))] = _edge_to_join_edge(best)

            # Parallel edges between the SAME two tables with different labels
            # (the doc's manages/works_in trap, stored as two MultiGraph edges
            # between department<->employee directly) never show up as an
            # "alternate route" below, since that only explores different node
            # sequences. Catch same-hop label divergence here instead.
            hop_labels = {e.get("label", "") for e in hop_variants}
            hop_pair_key = frozenset((a, b))
            if len(hop_variants) > 1 and len(hop_labels) > 1 and hop_pair_key not in seen_ambiguous_pairs:
                seen_ambiguous_pairs.add(hop_pair_key)
                ambiguous.extend([[_edge_to_join_edge(e)] for e in hop_variants])

        pair_key = frozenset((u, v))
        if pair_key in seen_ambiguous_pairs:
            continue
        primary_cost = _path_cost(join_graph, primary)
        primary_labels = _path_labels(join_graph, primary)

        # Look at the next few near-minimal-cost simple paths between u and v;
        # if one has a genuinely different set of edge labels, both real
        # relationships get surfaced instead of silently picking one.
        alt_path = None
        for i, path in enumerate(nx.shortest_simple_paths(simple_graph, u, v, weight=_weight)):
            if i >= 5 or _path_cost(join_graph, path) > primary_cost * 2 + 1e-9:
                break
            if _path_labels(join_graph, path) != primary_labels:
                alt_path = path
                break

        if alt_path is not None:
            seen_ambiguous_pairs.add(pair_key)
            all_nodes.update(alt_path)
            primary_join_edges = [
                primary_edges[frozenset((a, b))] for a, b in zip(primary, primary[1:])
            ]
            alt_join_edges = [
                _edge_to_join_edge(min(_edge_variants(join_graph, a, b), key=_edge_weight))
                for a, b in zip(alt_path, alt_path[1:])
            ]
            ambiguous.append(primary_join_edges)
            ambiguous.append(alt_join_edges)

    bridge_tables = sorted(all_nodes - set(candidates))
    return GraphExpansionResult(
        all_tables=sorted(all_nodes),
        bridge_tables=bridge_tables,
        join_paths=list(primary_edges.values()),
        ambiguous_paths=ambiguous,
    )
