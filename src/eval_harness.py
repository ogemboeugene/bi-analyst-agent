"""Execution-accuracy eval harness (defog-ai/sql-eval methodology).

For each golden question: run the agent, execute its SQL, execute the gold
SQL, compare result sets (order-insensitive). Writes evals/results.json.

Run: python -m src.eval_harness
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from .agent import ask
from .config import settings
from .db import run_query
from .guardrails import validate_and_harden

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "..", "evals", "golden.json")
RESULTS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "evals", "results.json"
)
HISTORY_PATH = os.path.join(
    os.path.dirname(__file__), "..", "evals", "history.jsonl"
)


def _normalize(rows: list[dict[str, Any]]) -> list[tuple]:
    """Order-insensitive comparable form; floats rounded to kill fp noise."""
    out = []
    for r in rows:
        row = []
        for v in r.values():
            row.append(round(v, 4) if isinstance(v, float) else v)
        out.append(tuple(sorted(row, key=repr)))
    return sorted(out, key=repr)


def results_match(gen_rows: list[dict], gold_rows: list[dict]) -> bool:
    return _normalize(gen_rows) == _normalize(gold_rows)


def run_eval() -> dict:
    with open(GOLDEN_PATH) as f:
        golden = json.load(f)

    results = []
    correct = 0
    for item in golden:
        t0 = time.time()
        record = {"id": item["id"], "category": item["category"], "ok": False}
        try:
            state = ask(item["question"])
            sql = state.get("sql", "")
            record["sql"] = sql
            record["attempts"] = state.get("attempts", 0)
            record["trace"] = state.get("trace", [])
            if not sql or state.get("answer", "").startswith("Could not"):
                record["reason"] = "agent_failed"
            else:
                hardened = validate_and_harden(sql)
                _, gen_rows = run_query(hardened, max_rows=10_000)
                if item.get("expect") == "fail":
                    record["reason"] = "should_have_failed"
                else:
                    _, gold_rows = run_query(item["gold_sql"], max_rows=10_000)
                    record["ok"] = results_match(gen_rows, gold_rows)
                    if not record["ok"]:
                        record["reason"] = "wrong_results"
        except Exception as e:
            record["reason"] = "exception"
            record["error"] = str(e)
        if item.get("expect") == "fail":
            # pass only when the agent declined/failed safely, never on success
            record["ok"] = record.get("reason") == "agent_failed"
        record["seconds"] = round(time.time() - t0, 1)
        correct += record["ok"]
        results.append(record)
        print(
            f"[{'PASS' if record['ok'] else 'FAIL'}] {item['id']} "
            f"({record.get('reason', 'match')}, {record['seconds']}s)"
        )

    by_cat: dict[str, list[bool]] = {}
    for r, item in zip(results, golden):
        by_cat.setdefault(item["category"], []).append(bool(r["ok"]))
    category_accuracy = {
        cat: round(sum(v) / len(v), 4) for cat, v in sorted(by_cat.items())
    }
    summary = {
        "accuracy": round(correct / len(golden), 4),
        "correct": correct,
        "total": len(golden),
        "model": settings.model,
        "by_category": category_accuracy,
        "results": results,
    }
    with open(RESULTS_PATH, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    with open(HISTORY_PATH, "a") as f:
        f.write(
            json.dumps(
                {
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "model": settings.model,
                    "accuracy": summary["accuracy"],
                }
            )
            + "\n"
        )
    print(f"\nAccuracy: {correct}/{len(golden)} = {summary['accuracy']:.0%}")
    for cat, acc in category_accuracy.items():
        print(f"  {cat}: {acc:.0%}")
    print(f"Wrote {RESULTS_PATH}")
    return summary


if __name__ == "__main__":
    run_eval()
