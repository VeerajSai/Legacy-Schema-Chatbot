from fastapi.testclient import TestClient

from api.server import app

client = TestClient(app)


def test_blocked_question_returns_403():
    resp = client.post("/chat", json={"question": "Delete all orders from the database", "role": "admin"})
    assert resp.status_code == 403
    assert resp.json()["blocked_reason"] is not None


def test_pipeline_exception_returns_5xx_not_raw_crash(monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("pipeline.orchestrator.answer_question", _boom)
    resp = client.post("/chat", json={"question": "How many orders were placed?", "role": "sales_analyst"})
    assert 500 <= resp.status_code < 600
    assert "error" in resp.json()
