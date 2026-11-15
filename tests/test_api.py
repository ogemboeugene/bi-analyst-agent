"""API tests via TestClient with canned LLM."""
import src.agent as agent
from fastapi.testclient import TestClient
from src.agent import SqlAnswer
from src.api import app


def _patch(monkeypatch):
    monkeypatch.setattr(
        agent,
        "chat_structured",
        lambda s, u, schema: SqlAnswer(
            sql="SELECT COUNT(*) AS n FROM orders", rationale="canned"
        ),
    )
    monkeypatch.setattr(agent, "chat", lambda s, u: "canned text")
    agent._index = None


def test_health():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_schema():
    client = TestClient(app)
    r = client.get("/schema")
    assert r.status_code == 200
    assert "CREATE TABLE orders" in r.json()["ddl"]


def test_ask_endpoint(monkeypatch, tmp_path):
    _patch(monkeypatch)
    monkeypatch.setattr("src.exemplars._STORE", str(tmp_path / "ex.jsonl"))
    client = TestClient(app)
    r = client.post(
        "/ask", json={"question": "how many orders", "thread_id": "api-t1"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rows"][0]["n"] == 900
    assert body["answer"] == "canned text"
    assert "narrate" in " ".join(body["trace"])


def test_ask_stream_events(monkeypatch, tmp_path):
    _patch(monkeypatch)
    monkeypatch.setattr("src.exemplars._STORE", str(tmp_path / "ex.jsonl"))
    client = TestClient(app)
    with client.stream(
        "POST",
        "/ask/stream",
        json={"question": "count orders", "thread_id": "api-t2"},
    ) as r:
        body = "".join(r.iter_text())
    assert r.status_code == 200
    assert '"node": "generate_sql"' in body
    assert '"node": "__done__"' in body
