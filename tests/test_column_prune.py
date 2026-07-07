from contracts.types import ColumnCard, GraphExpansionResult, JoinEdge, TableCard
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


def test_bridge_only_lookup_table_keeps_human_readable_column():
    # country_lkp is pulled in ONLY by bridge expansion (not part of the
    # original retrieval candidates) to complete a join path. The question
    # shares no tokens with its description/synonyms/column names, so the
    # normal topic filter would drop country_nm -- its only informational
    # column -- leaving the LLM unable to resolve "Germany" into a code.
    country_lkp = TableCard(
        table="country_lkp",
        module="reference",
        description="Country lookup: ISO country codes and names",
        row_count=200,
        columns=[
            ColumnCard(name="country_cd", dtype="TEXT", is_pk=True),
            ColumnCard(name="country_nm", dtype="TEXT"),
        ],
        synonyms=["countries"],
    )
    expansion = GraphExpansionResult(
        all_tables=["country_lkp"],
        bridge_tables=["country_lkp"],
    )
    pruned = prune_columns(
        "list all vendors headquartered in Germany",
        expansion,
        {"country_lkp": country_lkp},
    )

    kept = pruned.tables["country_lkp"]
    assert "country_cd" in kept  # PK
    assert "country_nm" in kept  # only human-readable column -- must survive


def test_schema_text_renders_ambiguous_paths_comment(table_cards):
    primary = JoinEdge("emp_dept_assign", "dept_id", "department", "dept_id", declared=True, label="works_in")
    alt = JoinEdge("department", "manager_emp_id", "employee", "emp_id", declared=True, label="manages")
    expansion = GraphExpansionResult(
        all_tables=["department"],
        ambiguous_paths=[[primary], [alt]],
    )
    pruned = prune_columns("who works in which department", expansion, table_cards)

    assert "ambiguous join" in pruned.schema_text
    assert "emp_dept_assign.dept_id = department.dept_id" in pruned.schema_text
    assert "department.manager_emp_id = employee.emp_id" in pruned.schema_text
