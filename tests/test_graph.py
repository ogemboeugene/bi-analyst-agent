"""End-to-end graph tests with a canned LLM — exercises real DuckDB
execution, real guardrails, real exemplar memory."""
import src.agent as agent
from src.agent import Intent, SqlAnswer


def _structured(sql):
    def fn(system, user, schema):
        if schema is Intent:
            return Intent(category="analytics_read", reason="test")
        return SqlAnswer(sql=sql, rationale="canned")

    return fn


class _FakeLLM:
    """Returns canned responses keyed on which prompt shape arrives."""

    def __init__(self, sql):
        self.sql = sql

    def chat(self, system, user):
        return "plan text" if "analysis plan" in system else "answer text"

    def chat_structured(self, system, user, schema):
        return _structured(self.sql)(system, user, schema)


def _patch(monkeypatch, sql):
    fake = _FakeLLM(sql)
    monkeypatch.setattr(agent, "chat", fake.chat)
    monkeypatch.setattr(agent, "chat_structured", fake.chat_structured)


def test_full_graph_happy_path(monkeypatch, tmp_path):
    sql = (
        "SELECT c.country, COUNT(*) AS n FROM orders o "
        "JOIN customers c ON o.customer_id = c.customer_id "
        "GROUP BY c.country"
    )
    _patch(monkeypatch, sql)
    monkeypatch.setattr(
        "src.exemplars._STORE", str(tmp_path / "ex.jsonl")
    )
    agent._index = None
    state = agent.ask("orders per country", thread_id="t1")
    assert state["error"] is None
    assert state["rows"]
    assert state["answer"] == "answer text"
    assert "remember:saved" in " ".join(state["trace"])
    # exemplar auto-saved
    import src.exemplars as ex

    assert any(e.sql.startswith("SELECT") for e in ex.load())


def test_self_correction_recovers(monkeypatch, tmp_path):
    """First SQL is broken; corrected SQL works — graph must retry."""
    monkeypatch.setattr(
        "src.exemplars._STORE", str(tmp_path / "ex.jsonl")
    )
    calls = {"n": 0}
    bad = "SELECT nonexistent_col FROM orders"
    good = "SELECT COUNT(*) AS n FROM orders"

    def structured(system, user, schema):
        if schema is Intent:
            return Intent(category="analytics_read", reason="test")
        calls["n"] += 1
        return SqlAnswer(
            sql=bad if calls["n"] == 1 else good, rationale="canned"
        )

    monkeypatch.setattr(agent, "chat_structured", structured)
    monkeypatch.setattr(
        agent, "chat", lambda s, u: "plan text" if "plan" in s else "ok"
    )
    agent._index = None
    state = agent.ask("how many orders", thread_id="t2")
    assert state["attempts"] >= 1
    assert state["rows"][0]["n"] == 900
    assert "self_correct" in " ".join(state["trace"])


def test_guardrail_rejection_routes_to_correct_or_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "src.exemplars._STORE", str(tmp_path / "ex.jsonl")
    )

    def structured(system, user, schema):
        if schema is Intent:
            return Intent(category="analytics_read", reason="sneaky")
        return SqlAnswer(sql="DROP TABLE orders", rationale="malicious")

    monkeypatch.setattr(agent, "chat_structured", structured)
    monkeypatch.setattr(agent, "chat", lambda s, u: "x")
    agent._index = None
    state = agent.ask("drop everything", thread_id="t3")
    # intent said read but SQL was hostile -> guardrail still blocked every
    # attempt -> fail node after max retries (defense in depth)
    assert "Could not answer" in state["answer"]
    assert "validate:guardrail" in " ".join(state["trace"])


def test_intent_refuses_write_request(monkeypatch, tmp_path):
    """Front-door check: destructive intent never reaches SQL generation."""
    monkeypatch.setattr(
        "src.exemplars._STORE", str(tmp_path / "ex.jsonl")
    )

    def structured(system, user, schema):
        if schema is Intent:
            return Intent(category="write_or_ddl", reason="delete request")
        return SqlAnswer(sql="SELECT 1", rationale="unused")

    monkeypatch.setattr(agent, "chat_structured", structured)
    monkeypatch.setattr(agent, "chat", lambda s, u: "x")
    agent._index = None
    state = agent.ask("delete all orders", thread_id="t4")
    assert "read-only analytics" in state["answer"]
    assert "refuse" in " ".join(state["trace"])
    assert "generate_sql" not in " ".join(state["trace"])


def test_resolve_question_passthrough_without_history():
    state = {"question": "standalone q", "trace": []}
    out = agent.resolve_question(state)
    assert "question" not in out  # unchanged
    assert "resolve:standalone" in out["trace"]
