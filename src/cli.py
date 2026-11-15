"""CLI entry.

  python -m src.cli "total revenue by country in 2025"
  python -m src.cli "and by segment?" --thread demo --stream
"""
from __future__ import annotations

import argparse

from .agent import ask, ask_stream


def main() -> None:
    p = argparse.ArgumentParser(prog="bi-analyst-agent")
    p.add_argument("question", nargs="+")
    p.add_argument("--thread", default="default", help="conversation thread id")
    p.add_argument("--stream", action="store_true", help="live node events")
    args = p.parse_args()
    q = " ".join(args.question)

    if args.stream:
        final = {}
        for event in ask_stream(q, thread_id=args.thread):
            for node, delta in event.items():
                print(f"[{node}]")
                final.update(delta)
        _print(final)
    else:
        _print(ask(q, thread_id=args.thread))


def _print(result) -> None:
    print(f"\nSQL:\n{result.get('sql')}\n")
    print(f"Answer:\n{result.get('answer')}\n")
    if result.get("chart_path"):
        print(f"Chart: {result['chart_path']}")
    print(f"Trace: {' -> '.join(result.get('trace', []))}")


if __name__ == "__main__":
    main()
