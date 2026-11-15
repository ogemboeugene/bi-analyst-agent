"""Agent memory: verified question->SQL exemplars, few-shot retrieved.

Mirrors vanna's agent-memory pattern: every verified success is stored,
and similar past pairs are surfaced into the generation prompt. This is
the single biggest accuracy lever in text-to-SQL — models imitate correct
prior answers far better than they extrapolate from bare DDL.

Store: data/exemplars.jsonl (committed, so the demo memory ships).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

_STORE = os.path.join(os.path.dirname(__file__), "..", "data", "exemplars.jsonl")
_TOKEN_RE = re.compile(r"[a-z_]+")


@dataclass
class Exemplar:
    question: str
    sql: str


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def load() -> list[Exemplar]:
    if not os.path.exists(_STORE):
        return []
    out = []
    with open(_STORE) as f:
        for line in f:
            line = line.strip()
            if line:
                d = json.loads(line)
                out.append(Exemplar(question=d["question"], sql=d["sql"]))
    return out


def retrieve(question: str, k: int = 3) -> list[Exemplar]:
    q_tokens = _tokens(question)
    ranked = sorted(
        load(),
        key=lambda e: len(_tokens(e.question) & q_tokens),
        reverse=True,
    )
    return [e for e in ranked[:k] if _tokens(e.question) & q_tokens]


def save(question: str, sql: str) -> None:
    """Persist a verified pair; skip near-duplicate questions."""
    q = question.strip()
    for e in load():
        if e.question.strip().lower() == q.lower():
            return
    os.makedirs(os.path.dirname(_STORE), exist_ok=True)
    with open(_STORE, "a") as f:
        f.write(json.dumps({"question": q, "sql": sql.strip()}) + "\n")


def few_shot_block(question: str, k: int = 3) -> str:
    """Prompt-ready block of similar verified pairs; empty if none."""
    hits = retrieve(question, k)
    if not hits:
        return ""
    parts = ["Verified examples from memory (adapt, don't copy):"]
    for e in hits:
        parts.append(f"Q: {e.question}\nSQL: {e.sql}")
    return "\n\n".join(parts)
