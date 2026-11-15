"""CLI entry: python -m src.cli "your question here"."""
from __future__ import annotations

import sys

from .agent import ask


def main() -> None:
    if len(sys.argv) < 2:
        print('usage: python -m src.cli "total revenue by country in 2025"')
        sys.exit(1)
    result = ask(" ".join(sys.argv[1:]))
    print(f"\nSQL:\n{result.get('sql')}\n")
    print(f"Answer:\n{result.get('answer')}\n")
    if result.get("chart_path"):
        print(f"Chart: {result['chart_path']}")
    print(f"Trace: {' -> '.join(result.get('trace', []))}")


if __name__ == "__main__":
    main()
