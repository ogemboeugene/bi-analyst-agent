"""Demo dataset: deterministic synthetic retail data in DuckDB.

Fully self-contained — no downloads. Swap `connect()` target in db.py
to point at a real warehouse later.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

import duckdb

from .config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    name VARCHAR,
    segment VARCHAR,
    country VARCHAR,
    signed_up DATE
);
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY,
    name VARCHAR,
    category VARCHAR,
    unit_price DECIMAL(10,2)
);
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id),
    order_date DATE,
    status VARCHAR
);
CREATE TABLE IF NOT EXISTS order_items (
    order_id INTEGER REFERENCES orders(order_id),
    product_id INTEGER REFERENCES products(product_id),
    quantity INTEGER,
    unit_price DECIMAL(10,2)
);
"""

_SEGMENTS = ["consumer", "sme", "enterprise"]
_COUNTRIES = ["Kenya", "Uganda", "Tanzania", "Rwanda", "Nigeria", "Ghana"]
_CATEGORIES = ["beverages", "staples", "household", "personal_care", "electronics"]
_STATUSES = ["completed", "completed", "completed", "returned", "cancelled"]


def bootstrap(path: str = settings.db_path) -> duckdb.DuckDBPyConnection:
    """Create the demo DB if empty; return a connection."""
    con = duckdb.connect(path)
    con.execute(_SCHEMA)
    if con.execute("SELECT COUNT(*) FROM customers").fetchone()[0] > 0:
        return con

    rng = random.Random(42)
    for i in range(1, 81):
        con.execute(
            "INSERT INTO customers VALUES (?, ?, ?, ?, ?)",
            [
                i,
                f"Customer {i:03d}",
                rng.choice(_SEGMENTS),
                rng.choice(_COUNTRIES),
                date(2024, 1, 1) + timedelta(days=rng.randint(0, 400)),
            ],
        )
    products = [
        (i, f"{cat.title()} Item {i}", cat, round(rng.uniform(2, 500), 2))
        for i, cat in enumerate(_CATEGORIES * 8, start=1)
    ]
    con.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", products)
    oid = 0
    for i in range(1, 901):
        oid += 1
        cid = rng.randint(1, 80)
        odate = date(2025, 1, 1) + timedelta(days=rng.randint(0, 364))
        status = rng.choice(_STATUSES)
        con.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?)", [oid, cid, odate, status]
        )
        for _ in range(rng.randint(1, 4)):
            pid = rng.randint(1, len(products))
            price = products[pid - 1][3]
            con.execute(
                "INSERT INTO order_items VALUES (?, ?, ?, ?)",
                [oid, pid, rng.randint(1, 10), price],
            )
    return con
