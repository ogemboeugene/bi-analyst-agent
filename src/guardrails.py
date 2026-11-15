"""Guardrails: keep generated SQL safe before it touches the database.

- single statement, read-only (SELECT/WITH/EXPLAIN)
- auto-inject LIMIT when missing
- parse-level check via sqlglot (dialect-aware)
"""
from __future__ import annotations

import sqlglot
from sqlglot import exp

from .config import settings


class GuardrailError(Exception):
    """Raised when generated SQL fails safety checks."""


def validate_and_harden(sql: str, max_rows: int = settings.max_rows) -> str:
    sql = sql.strip().rstrip(";")
    if not sql:
        raise GuardrailError("Empty SQL.")

    try:
        statements = list(sqlglot.parse(sql, read="duckdb"))
    except sqlglot.errors.ParseError as e:
        raise GuardrailError(f"SQL does not parse: {e}") from e

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise GuardrailError("Exactly one statement is allowed.")

    stmt = statements[0]
    if not isinstance(stmt, (exp.Select, exp.Union, exp.Subquery, exp.With)):
        raise GuardrailError(
            f"Only read-only SELECT/WITH queries are allowed, got "
            f"{type(stmt).__name__}."
        )

    # No nested write expressions anywhere in the tree
    forbidden = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create)
    for node in stmt.walk():
        if isinstance(node, forbidden):
            raise GuardrailError("Write/DDL operations are not allowed.")

    if stmt.args.get("limit") is None and not isinstance(stmt, exp.With):
        stmt = stmt.limit(max_rows)

    return stmt.sql(dialect="duckdb")
