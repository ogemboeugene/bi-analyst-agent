"""The agent: a LangGraph state machine.

plan → retrieve_schema → generate_sql → validate → execute
           ↑                                   │
           └──── self_correct ←── on error ←────┘
                                      │
                   success → chart → narrate → END
"""
from __future__ import annotations

import re
from typing import Any, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from .config import settings
from .db import explain, run_query
from .guardrails import GuardrailError, validate_and_harden
from .llm import chat
from .prompts import (
    CORRECT_SQL_PROMPT,
    GENERATE_SQL_PROMPT,
    NARRATE_PROMPT,
    PLAN_PROMPT,
)
from .schema_rag import SchemaIndex


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
    trace: list[str]


_index: SchemaIndex | None = None


def _index_or_create() -> SchemaIndex:
    global _index
    if _index is None:
        _index = SchemaIndex()
    return _index


def _trace(state: AgentState, msg: str) -> dict:
    return {"trace": state.get("trace", []) + [msg]}


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
    raw = chat(
        GENERATE_SQL_PROMPT.format(schema=state["schema_context"]), user
    )
    sql = _strip_fences(raw)
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
    raw = chat(
        CORRECT_SQL_PROMPT.format(
            schema=state["schema_context"],
            sql=state["sql"],
            error=state["error"],
        ),
        f"Question: {state['question']}",
    )
    return {
        "sql": _strip_fences(raw),
        "attempts": attempts,
        "error": None,
        **_trace(state, f"self_correct:attempt {attempts}"),
    }


def chart(state: AgentState) -> dict:
    import os

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows, cols = state.get("rows", []), state.get("columns", [])
    if len(rows) < 2 or len(cols) < 2:
        return {"chart_path": None, **_trace(state, "chart:skipped")}

    num_cols = [
        c for c in cols if all(isinstance(r.get(c), (int, float)) for r in rows)
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
    return {"answer": raw, **_trace(state, "narrate")}


def _strip_fences(text: str) -> str:
    m = re.search(r"```(?:sql)?\s*(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip()


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
    g.add_node("plan", plan)
    g.add_node("generate_sql", generate_sql)
    g.add_node("validate", validate)
    g.add_node("execute", execute)
    g.add_node("self_correct", self_correct)
    g.add_node("chart", chart)
    g.add_node("narrate", narrate)
    g.add_node("fail", fail)

    g.add_edge(START, "plan")
    g.add_edge("plan", "generate_sql")
    g.add_edge("generate_sql", "validate")
    g.add_conditional_edges("validate", _route_after_validate)
    g.add_conditional_edges("execute", _route_after_execute)
    g.add_edge("self_correct", "validate")
    g.add_edge("chart", "narrate")
    g.add_edge("narrate", END)
    g.add_edge("fail", END)
    return g


_compiled = None


def ask(question: str) -> AgentState:
    global _compiled
    if _compiled is None:
        _compiled = build_graph().compile()
    return _compiled.invoke({"question": question, "attempts": 0, "trace": []})
