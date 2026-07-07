import dataclasses

from contracts.types import ColumnCard, JoinEdge, TableCard
from contracts.llm_client import StubLLMClient, get_llm_client
from contracts.rbac import allowed_modules, filter_tables_by_role


def test_table_card_roundtrip():
    card = TableCard(
        table="ord_hdr", module="sales", description="Order headers", row_count=100,
        columns=[ColumnCard(name="ord_id", dtype="INTEGER", is_pk=True)],
        synonyms=["orders"],
    )
    d = card.to_dict()
    restored = TableCard.from_dict(d)
    assert restored == card
    assert "ord_id" in card.to_prompt_text()
    assert "sales" in card.to_index_text()


def test_join_edge_is_frozen_shape():
    edge = JoinEdge(left_table="a", left_col="id", right_table="b", right_col="a_id", declared=True)
    assert dataclasses.asdict(edge)["declared"] is True


def test_rbac_filters_by_role():
    allowed = allowed_modules("hr_admin")
    assert allowed == {"hr", "core"}
    filtered = filter_tables_by_role({"employee": "hr", "gl_account": "finance"}, "hr_admin")
    assert filtered == {"employee"}


def test_stub_llm_client_is_deterministic_and_offline():
    client = StubLLMClient(strong_responses={"orders": "SELECT * FROM ord_hdr"})
    resp = client.call_strong("system", "how many orders?")
    assert resp.text == "SELECT * FROM ord_hdr"
    assert len(client.calls) == 1


def test_get_llm_client_falls_back_to_stub_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = get_llm_client()
    assert isinstance(client, StubLLMClient)
