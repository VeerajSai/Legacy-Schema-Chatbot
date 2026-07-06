from contracts.types import GraphExpansionResult, JoinEdge
from retrieval.column_prune import prune_columns


def test_keys_kept_irrelevant_non_key_column_dropped(table_cards):
    # question shares no tokens at all with "qty", but does share tokens with
    # unit_price/line_status/description ("order", "line", "unit", "price").
    question = "What is the unit price for each order line?"
    expansion = GraphExpansionResult(all_tables=["ord_dtl_2"])
    pruned = prune_columns(question, expansion, table_cards)

    kept = pruned.tables["ord_dtl_2"]
    # PK and FKs always survive, regardless of relevance to the question
    assert "ord_dtl_id" in kept  # PK
    assert "ord_id" in kept      # FK -> ord_hdr
    assert "item_id" in kept     # FK -> item_mst
    # relevant non-key column kept
    assert "unit_price" in kept
    # irrelevant non-key column dropped
    assert "qty" not in kept


def test_schema_text_renders_join_path_comment(table_cards):
    expansion = GraphExpansionResult(
        all_tables=["ord_hdr", "ord_dtl_2"],
        join_paths=[JoinEdge("ord_dtl_2", "ord_id", "ord_hdr", "ord_id", declared=True, label="has_line_item")],
    )
    pruned = prune_columns("total value per order", expansion, table_cards)

    assert "ord_hdr(" in pruned.schema_text
    assert "ord_dtl_2(" in pruned.schema_text
    assert "-- join path: ord_dtl_2.ord_id = ord_hdr.ord_id" in pruned.schema_text


def test_unrelated_table_with_no_overlap_still_keeps_only_keys(table_cards):
    # gl_account has nothing to do with a customer question; description
    # overlap is false, so only PK survives (no fallback triggers).
    expansion = GraphExpansionResult(all_tables=["gl_account"])
    pruned = prune_columns("show customer order totals by region", expansion, table_cards)
    assert pruned.tables["gl_account"] == ["gl_acct_id"]
