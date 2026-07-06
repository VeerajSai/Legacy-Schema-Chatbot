"""Orchestrator integration tests. Retrieval/graph/column-pruning and the
catalog loaders are owned by parallel agents and may not exist (fully) yet,
so we inject fake modules into sys.modules / monkeypatch the catalog loader
attributes rather than depending on their real implementations."""
import sys
import types

import networkx as nx
import pytest

from contracts.llm_client import StubLLMClient
from contracts.types import ColumnCard, GraphExpansionResult, PrunedSchema, RetrievalResult, TableCard
from pipeline.orchestrator import answer_question

ORD_HDR = TableCard(
    table="ord_hdr",
    module="sales",
    description="Order headers",
    row_count=4000,
    columns=[
        ColumnCard(name="ord_id", dtype="INTEGER", is_pk=True),
        ColumnCard(name="cust_id", dtype="INTEGER"),
        ColumnCard(name="status_cd", dtype="TEXT"),
    ],
)
TABLE_CARDS = {"ord_hdr": ORD_HDR}


def _install_fake_module(monkeypatch, name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, name, mod)
    return mod


@pytest.fixture
def mock_deps(monkeypatch, tmp_path):
    # Keep cache/log writes out of the real repo during tests.
    import pipeline.cache as cache_mod
    import pipeline.logger as logger_mod
    monkeypatch.setattr(cache_mod, "CACHE_DB_PATH", tmp_path / "cache.db")
    monkeypatch.setattr(logger_mod, "PIPELINE_LOG_PATH", tmp_path / "pipeline.jsonl")

    retrieval_result = RetrievalResult(candidate_tables=["ord_hdr"], scores={"ord_hdr": 1.0})
    graph_result = GraphExpansionResult(all_tables=["ord_hdr"])
    pruned = PrunedSchema(
        tables={"ord_hdr": ["ord_id", "cust_id", "status_cd"]},
        schema_text="ord_hdr(ord_id PK, cust_id FK, status_cd)",
    )
    join_graph = nx.Graph()
    join_graph.add_edge("ord_hdr", "cust_mst")  # trivial 2-node graph; unused since expand is mocked

    _install_fake_module(
        monkeypatch, "retrieval.hybrid_retrieve",
        retrieve_tables=lambda *a, **k: retrieval_result,
    )
    _install_fake_module(
        monkeypatch, "retrieval.graph_expand",
        expand_with_graph=lambda *a, **k: graph_result,
    )
    _install_fake_module(
        monkeypatch, "retrieval.column_prune",
        prune_columns=lambda *a, **k: pruned,
    )

    import catalog.build_catalog as catalog_mod
    monkeypatch.setattr(catalog_mod, "load_table_cards", lambda: TABLE_CARDS, raising=False)
    monkeypatch.setattr(catalog_mod, "load_join_graph", lambda: join_graph, raising=False)


def test_end_to_end_count_query_runs_against_live_db(mock_deps):
    llm = StubLLMClient(
        cheap_responses={
            "How many orders are there": '{"rewritten": "how many orders are there", "ambiguous": false, "clarifying_question": ""}',
        },
        strong_responses={
            "how many orders are there": "```sql\nSELECT COUNT(*) FROM ord_hdr\n```",
        },
    )
    ctx = answer_question("How many orders are there?", user_id="u1", role="sales_analyst", llm=llm)

    assert ctx.blocked_reason is None
    assert ctx.clarification_question is None
    assert ctx.sql_candidate is not None
    assert ctx.validation is not None and ctx.validation.is_valid
    assert ctx.execution is not None and ctx.execution.success
    assert ctx.execution.rows == [(4000,)]
    assert ctx.answer is not None


def test_end_to_end_distinct_query_runs_against_live_db(mock_deps):
    llm = StubLLMClient(
        cheap_responses={
            "What are the order statuses": '{"rewritten": "what are the order statuses", "ambiguous": false, "clarifying_question": ""}',
        },
        strong_responses={
            "what are the order statuses": "```sql\nSELECT DISTINCT status_cd FROM ord_hdr\n```",
        },
    )
    ctx = answer_question("What are the order statuses?", user_id="u2", role="admin", llm=llm)

    assert ctx.sql_candidate is not None
    assert ctx.validation.is_valid
    assert ctx.execution.success
    assert ctx.execution.row_count > 0
    assert ctx.answer is not None


def test_guardrail_blocks_dml_intent_before_generation(mock_deps):
    llm = StubLLMClient()
    ctx = answer_question("Delete all orders from last month", user_id="u3", role="admin", llm=llm)

    assert ctx.blocked_reason is not None
    assert ctx.sql_candidate is None
    assert len(llm.calls) == 0  # never reached understanding/generation


def test_ambiguity_gate_returns_early_with_clarification(mock_deps):
    llm = StubLLMClient(
        cheap_responses={
            "What's our revenue": '{"rewritten": "what is our revenue", "ambiguous": true, "clarifying_question": "Do you mean gross or net revenue?"}',
        },
    )
    ctx = answer_question("What's our revenue?", user_id="u4", role="admin", llm=llm)

    assert ctx.clarification_question == "Do you mean gross or net revenue?"
    assert ctx.sql_candidate is None
    assert ctx.execution is None
