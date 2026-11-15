"""Training-data generation for the QLoRA stretch.

Strategy (the honest one): SQL is generated PROGRAMMATICALLY from templates
over the schema — guaranteed correct. The teacher LLM only PARAPHRASES each
skeleton question into natural English — it can never produce wrong SQL.

Output: data/train.jsonl in chat SFT format mirroring inference-time input:
  system = GENERATE_SQL_PROMPT + schema + glossary
  user   = natural question
  assistant = {"sql": ..., "rationale": ...}  (the SqlAnswer contract)

Run:  python -m src.gen_training_data            # ~small sample
      python -m src.gen_training_data --full     # the full sweep
"""
from __future__ import annotations

import argparse
import itertools
import json
import os

from .db import schema_ddl
from .exemplars import few_shot_block  # noqa: F401  (documents reuse path)
from .llm import chat
from .prompts import GENERATE_SQL_PROMPT
from .semantics import GLOSSARY

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "train.jsonl")

# --- programmatic skeletons: (skeleton_question, correct_sql) ------------

_METRICS = [
    ("revenue", "SUM(oi.quantity * oi.unit_price)", True),
    ("units sold", "SUM(oi.quantity)", True),
    ("order count", "COUNT(DISTINCT o.order_id)", True),
]
_DIMS = [
    ("by country", "c.country", "customers c ON o.customer_id = c.customer_id"),
    ("by segment", "c.segment", "customers c ON o.customer_id = c.customer_id"),
    ("by product category", "p.category", "products p ON oi.product_id = p.product_id"),
    ("by month", "strftime('%Y-%m', o.order_date)", None),
]


def skeletons() -> list[tuple[str, str]]:
    out = []
    for metric_label, agg, completed in _METRICS:
        for dim_label, dim, join in _DIMS:
            joins = "JOIN order_items oi ON o.order_id = oi.order_id"
            if join:
                joins += f" JOIN {join}"
            where = "WHERE o.status = 'completed'" if completed else ""
            sql = (
                f"SELECT {dim} AS dim, {agg} AS metric FROM orders o {joins} "
                f"{where} GROUP BY {dim} ORDER BY metric DESC LIMIT 50"
            )
            out.append((f"{metric_label} {dim_label}", sql))
    # status counts and simple scans
    out += [
        ("orders by status", "SELECT status, COUNT(*) AS n FROM orders GROUP BY status ORDER BY n DESC"),
        ("customers by segment", "SELECT segment, COUNT(*) AS n FROM customers GROUP BY segment ORDER BY n DESC"),
        ("products by category", "SELECT category, COUNT(*) AS n FROM products GROUP BY category ORDER BY n DESC"),
        ("revenue lost to cancelled orders", "SELECT SUM(oi.quantity * oi.unit_price) AS lost FROM orders o JOIN order_items oi ON o.order_id = oi.order_id WHERE o.status = 'cancelled'"),
        ("average items per order", "SELECT AVG(items) AS avg_items FROM (SELECT order_id, COUNT(*) AS items FROM order_items GROUP BY order_id) t"),
    ]
    return out


def paraphrase(skeleton_q: str) -> list[str]:
    """Teacher rewrites each skeleton into 2 natural phrasings."""
    out = chat(
        "You generate natural BI questions. Return exactly 2 rewrites of the "
        "given question — different phrasing, same intent, one per line, no "
        "numbering, no punctuation changes to meaning.",
        skeleton_q,
    )
    lines = [l.strip("-• \t") for l in out.splitlines() if l.strip()]
    return [skeleton_q] + lines[:2]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--full", action="store_true", help="LLM paraphrase every skeleton")
    args = p.parse_args()

    system = GENERATE_SQL_PROMPT.format(schema=schema_ddl() + "\n\n" + GLOSSARY)
    rows = []
    for skel_q, sql in skeletons():
        variants = paraphrase(skel_q) if args.full else [skel_q]
        for q in variants:
            rows.append(
                {
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": q},
                        {
                            "role": "assistant",
                            "content": json.dumps(
                                {"sql": sql, "rationale": "template-verified"}
                            ),
                        },
                    ]
                }
            )
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {len(rows)} examples -> {OUT_PATH}")


if __name__ == "__main__":
    main()
