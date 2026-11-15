"""The agent: a LangGraph state machine.

plan → retrieve_schema → generate_sql → validate → execute
           ↑                                   │
           └──── self_correct ←── on error ←────┘
                                      │
                   success → chart → narrate → END
"""
from __future__ import annotations

from typing import Any, Optional, TypedDict

from pydantic import BaseModel, Field

from langgraph.graph import END, START, StateGraph

from .config import settings
from .db import explain, run_query
from .exemplars import few_shot_block, save as save_exemplar
from .guardrails import GuardrailError, validate_and_harden
from .llm import chat, chat_structured
from .prompts import (
    CORRECT_SQL_PROMPT,
    GENERATE_SQL_PROMPT,
    NARRATE_PROMPT,
    PLAN_PROMPT,
    REWRITE_PROMPT,
)
from .schema_rag import SchemaIndex


class SqlAnswer(BaseModel):
    sql: str = Field(description="One read-only SELECT query, DuckDB dialect")
    rationale: str = Field(description="One sentence: why this answers the question")


class AgentState(TypedDict, total=False):
    question: str
    plan: str
    schema_context: str
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    error: Optional[str]
    attempts: int
    chart_path: Optional[str]
    answer: str
    history: list[str]
    trace: list[str]


_index: SchemaIndex | None = None


def _index_or_create() -> SchemaIndex:
    global _index
    if _index is None:
        _index = SchemaIndex()
    return _index


def _trace(state: AgentState, msg: str) -> dict:
    return {"trace": state.get("trace", []) + [msg]}


def resolve_question(state: AgentState) -> dict:
    """Rewrite follow-ups into standalone questions using chat history."""
    history = state.get("history") or []
    q = state["question"]
    if not history:
        return _trace(state, "resolve:standalone")
    rewritten = chat(
        REWRITE_PROMPT,
        f"History:\n" + "\n".join(history[-6:]) + f"\n\nFollow-up: {q}",
    )
    return {"question": rewritten, **_trace(state, f"resolve:rewrote -> {rewritten[:60]}")}


def plan(state: AgentState) -> dict:
    q = state["question"]
    schema_ctx = _index_or_create().retrieve(q)
    out = chat(PLAN_PROMPT, f"Question: {q}\n\nSchema:\n{schema_ctx}")
    return {"plan": out, "schema_context": schema_ctx, **_trace(state, "plan")}


def generate_sql(state: AgentState) -> dict:
    q = state["question"]
    user = (
        f"Question: {q}\n\nPlan: {state['plan']}"
        if state.get("plan")
        else f"Question: {q}"
    )
    memory = few_shot_block(q)
    ans: SqlAnswer = chat_structured(
        GENERATE_SQL_PROMPT.format(schema=state["schema_context"]),
        f"{user}\n\n{memory}" if memory else user,
        SqlAnswer,
    )
    sql = ans.sql.strip()
    return {"sql": sql, "error": None, **_trace(state, "generate_sql")}


def validate(state: AgentState) -> dict:
    try:
        hardened = validate_and_harden(state["sql"])
    except GuardrailError as e:
        return {"error": str(e), **_trace(state, f"validate:guardrail {e}")}
    try:
        explain(hardened)  # fail fast on bad plans before real execution
    except Exception as e:
        return {"error": str(e), **_trace(state, f"validate:plan {e}")}
    return {"sql": hardened, "error": None, **_trace(state, "validate:ok")}


def execute(state: AgentState) -> dict:
    try:
        cols, rows = run_query(state["sql"])
        return {
            "columns": cols,
            "rows": rows,
            "error": None,
            **_trace(state, f"execute:{len(rows)} rows"),
        }
    except Exception as e:
        return {"error": str(e), **_trace(state, f"execute:fail {e}")}


def self_correct(state: AgentState) -> dict:
    attempts = state.get("attempts", 0) + 1
    ans: SqlAnswer = chat_structured(
        CORRECT_SQL_PROMPT.format(
            schema=state["schema_context"],
            sql=state["sql"],
            error=state["error"],
        ),
        f"Question: {state['question']}",
        SqlAnswer,
    )
    return {
        "sql": ans.sql.strip(),
        "attempts": attempts,
        "error": None,
        **_trace(state, f"self_correct:attempt {attempts}"),
    }


def chart(state: AgentState) -> dict:
    import os
    from decimal import Decimal

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows, cols = state.get("rows", []), state.get("columns", [])
    if len(rows) < 2 or len(cols) < 2:
        return {"chart_path": None, **_trace(state, "chart:skipped")}

    num_cols = [
        c
        for c in cols
        if all(isinstance(r.get(c), (int, float, Decimal)) for r in rows)
    ]
    label_cols = [c for c in cols if c not in num_cols]
    if not num_cols or not label_cols:
        return {"chart_path": None, **_trace(state, "chart:skipped")}

    os.makedirs(settings.output_dir, exist_ok=True)
    path = os.path.join(settings.output_dir, "chart.png")
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(
        [str(r[label_cols[0]]) for r in rows[:20]],
        [r[num_cols[0]] for r in rows[:20]],
    )
    ax.set_xlabel(label_cols[0])
    ax.set_ylabel(num_cols[0])
    ax.set_title(state["question"][:80])
    plt.xticks(rotation=45, ha="right")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return {"chart_path": path, **_trace(state, "chart:saved")}


def narrate(state: AgentState) -> dict:
    preview = state.get("rows", [])[:10]
    raw = chat(
        NARRATE_PROMPT,
        f"Question: {state['question']}\nSQL: {state['sql']}\n"
        f"Columns: {state.get('columns')}\nRows (preview): {preview}",
    )
    history = (state.get("history") or []) + [
        f"Q: {state['question']} | A: {raw[:200]}"
    ]
    return {"answer": raw, "history": history, **_trace(state, "narrate")}


def remember(state: AgentState) -> dict:
    """Persist verified question->SQL pairs as future few-shot exemplars."""
    if state.get("rows") and state.get("sql"):
        save_exemplar(state["question"], state["sql"])
        return _trace(state, "remember:saved")
    return _trace(state, "remember:skipped")


def _route_after_execute(state: AgentState) -> str:
    if state.get("error") and state.get("attempts", 0) < settings.max_attempts:
        return "self_correct"
    if state.get("error"):
        return "fail"
    return "chart"


def _route_after_validate(state: AgentState) -> str:
    if state.get("error") and state.get("attempts", 0) < settings.max_attempts:
        return "self_correct"
    if state.get("error"):
        return "fail"
    return "execute"


def fail(state: AgentState) -> dict:
    return {
        "answer": f"Could not answer after {state.get('attempts', 0)} retries. "
        f"Last error: {state.get('error')}",
        **_trace(state, "fail"),
    }


def build_graph() -> StateGraph:
    g = StateGraph(AgentState)
    g.add_node("resolve_question", resolve_question)
    g.add_node("plan", plan)
    g.add_node("generate_sql", generate_sql)
    g.add_node("validate", validate)
    g.add_node("execute", execute)
    g.add_node("self_correct", self_correct)
    g.add_node("chart", chart)
    g.add_node("narrate", narrate)
    g.add_node("remember", remember)
    g.add_node("fail", fail)

    g.add_edge(START, "resolve_question")
    g.add_edge("resolve_question", "plan")
    g.add_edge("plan", "generate_sql")
    g.add_edge("generate_sql", "validate")
    g.add_conditional_edges("validate", _route_after_validate)
    g.add_conditional_edges("execute", _route_after_execute)
    g.add_edge("self_correct", "validate")
    g.add_edge("chart", "narrate")
    g.add_edge("narrate", "remember")
    g.add_edge("remember", END)
    g.add_edge("fail", END)
    return g


_compiled = None


def _get_graph():
    global _compiled
    if _compiled is None:
        from langgraph.checkpoint.memory import MemorySaver

        _compiled = build_graph().compile(checkpointer=MemorySaver())
    return _compiled


def ask(question: str, thread_id: str = "default") -> AgentState:
    """Run one turn. Same thread_id = shared conversation history."""
    return _get_graph().invoke(
        {"question": question, "attempts": 0, "trace": []},
        config={"configurable": {"thread_id": thread_id}},
    )


def ask_stream(question: str, thread_id: str = "default"):
    """Yield (node, state-delta) events as the graph executes."""
    yield from _get_graph().stream(
        {"question": question, "attempts": 0, "trace": []},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode="updates",
    )
