from contracts.types import RetrievalResult
from retrieval.graph_expand import expand_with_graph


def test_bridge_tables_surface_unnamed_join_path(table_cards, join_graph):
    # "region" is literal in the question so region_lkp gets retrieved
    # directly; item_mst is retrieved for "value". Nobody named cust_addr or
    # ord_dtl_2, but they sit on the only path connecting the retrieved tables
    # and must be surfaced as bridge tables.
    retrieval = RetrievalResult(candidate_tables=["ord_hdr", "cust_mst", "item_mst", "region_lkp"])
    expansion = expand_with_graph(retrieval, join_graph, table_cards)

    assert "cust_addr" in expansion.bridge_tables
    assert "ord_dtl_2" in expansion.bridge_tables
    assert set(retrieval.candidate_tables) <= set(expansion.all_tables)
    # bridge tables augment, never replace, the retrieved candidates
    assert set(expansion.bridge_tables).isdisjoint(retrieval.candidate_tables)


def test_disjoint_path_trap_surfaces_both_labeled_paths(table_cards, join_graph):
    # department<->employee has two real declared FKs with different meaning:
    # department.manager_emp_id -> employee.emp_id ("manages"), and the
    # emp_dept_assign bridge ("works_in"). A correct implementation must not
    # silently collapse to just the cheaper direct edge.
    retrieval = RetrievalResult(candidate_tables=["department", "employee"])
    expansion = expand_with_graph(retrieval, join_graph, table_cards)

    assert len(expansion.ambiguous_paths) == 2
    all_labels = {edge.label for path in expansion.ambiguous_paths for edge in path}
    assert "manages" in all_labels
    assert "works_in" in all_labels


def test_no_ambiguity_when_only_one_real_path_exists(table_cards, join_graph):
    # ord_hdr <-> ord_dtl_2 has exactly one declared FK between them - nothing
    # to disambiguate, so no spurious ambiguous_paths entries.
    retrieval = RetrievalResult(candidate_tables=["ord_hdr", "ord_dtl_2"])
    expansion = expand_with_graph(retrieval, join_graph, table_cards)

    assert expansion.ambiguous_paths == []
    assert expansion.join_paths
