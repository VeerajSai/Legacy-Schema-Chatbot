from retrieval.bm25_index import BM25Index
from retrieval.embed_index import EmbedIndex
from retrieval.hybrid_retrieve import retrieve_tables


def test_bm25_wins_on_exact_jargon_token(table_cards):
    # "ord_dtl_2" is a literal, cryptic table name — no paraphrase, no synonym.
    # BM25 must catch the exact token even though a topically-similar decoy
    # (ord_hdr, also order-related) has no such literal overlap.
    question = "show me ord_dtl_2 records please"
    bm25 = BM25Index()
    bm25.build(table_cards)
    scores = bm25.scores(question)
    assert scores["ord_dtl_2"] > scores["ord_hdr"]
    assert bm25.query(question, top_n=3)[0] == "ord_dtl_2"


def test_hybrid_retrieve_surfaces_exact_jargon_table(table_cards):
    result = retrieve_tables("show me ord_dtl_2 records please", table_cards, role="admin")
    assert "ord_dtl_2" in result.bm25_top
    assert "ord_dtl_2" in result.candidate_tables


def test_dense_alone_can_be_fooled_by_paraphrase_while_bm25_holds_the_line(table_cards):
    # Sanity check on the premise of the hybrid design: a semantically loaded
    # question about "line items" scores both order tables reasonably on
    # dense similarity, but only BM25 (via synonyms indexed in to_index_text)
    # nails the specific detail table.
    dense = EmbedIndex()
    dense.build(table_cards)
    bm25 = BM25Index()
    bm25.build(table_cards)
    question = "order line items with quantity and unit price"
    assert bm25.scores(question)["ord_dtl_2"] > 0
    # dense also finds it plausible (doesn't need to win, just be in the mix)
    assert "ord_dtl_2" in dense.query(question, top_n=5)


def test_rbac_restricts_candidates_to_allowed_modules(table_cards):
    # sales_analyst is only allowed sales/crm/inventory/core (config/rbac.yaml).
    # Ask a question squarely about HR data — employee/department would win on
    # every retrieval signal if not filtered out first.
    question = "Which employee manages which department?"
    result = retrieve_tables(question, table_cards, role="sales_analyst")

    restricted_tables = {"employee", "department", "emp_dept_assign"}  # module=hr
    assert not (restricted_tables & set(result.candidate_tables))
    assert not (restricted_tables & set(result.bm25_top))
    assert not (restricted_tables & set(result.dense_top))

    # same question, admin role: hr tables are fair game and should show up.
    admin_result = retrieve_tables(question, table_cards, role="admin")
    assert restricted_tables & set(admin_result.candidate_tables)
