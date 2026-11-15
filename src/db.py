"""Database access layer."""
from __future__ import annotations

import duckdb

from .config import settings
from .data import bootstrap


def connect() -> duckdb.DuckDBPyConnection:
    return bootstrap(settings.db_path)


def run_query(sql: str, max_rows: int = settings.max_rows):
    """Execute SQL, return (columns, rows-as-dicts). Raises on failure."""
    con = connect()
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchmany(max_rows)]
    return cols, rows


def explain(sql: str) -> str:
    con = connect()
    plan = con.execute(f"EXPLAIN {sql}").fetchall()
    return "\n".join(r[1] for r in plan)


def schema_ddl() -> str:
    """Return CREATE TABLE statements for every table — agent's schema view."""
    con = connect()
    tables = [
        r[0]
        for r in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='main' ORDER BY table_name"
        ).fetchall()
    ]
    parts = []
    for t in tables:
        cols = con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            f"WHERE table_name='{t}' ORDER BY ordinal_position"
        ).fetchall()
        col_sql = ",\n  ".join(f"{c} {dt}" for c, dt in cols)
        parts.append(f"CREATE TABLE {t} (\n  {col_sql}\n);")
    return "\n\n".join(parts)
