import pytest

from src.guardrails import GuardrailError, validate_and_harden


def test_select_gets_limit():
    out = validate_and_harden("SELECT * FROM orders")
    assert "LIMIT 200" in out
    assert out.startswith("SELECT")


def test_cte_gets_limit_on_outer_select():
    out = validate_and_harden("WITH t AS (SELECT * FROM orders) SELECT * FROM t")
    assert "LIMIT 200" in out


def test_existing_limit_preserved():
    out = validate_and_harden("SELECT * FROM orders LIMIT 5")
    assert "LIMIT 5" in out
    assert "LIMIT 200" not in out


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE orders",
        "INSERT INTO orders VALUES (1,1,'2025-01-01','x')",
        "UPDATE orders SET status='x'",
        "DELETE FROM orders",
        "CREATE TABLE t (a INT)",
        "ALTER TABLE orders ADD COLUMN x INT",
    ],
)
def test_write_and_ddl_blocked(sql):
    with pytest.raises(GuardrailError):
        validate_and_harden(sql)


def test_multi_statement_blocked():
    with pytest.raises(GuardrailError):
        validate_and_harden("SELECT 1; SELECT 2")


def test_empty_blocked():
    with pytest.raises(GuardrailError):
        validate_and_harden("   ")


def test_unparseable_blocked():
    with pytest.raises(GuardrailError):
        validate_and_harden("SELEC * FORM orders WHERE")


def test_nested_write_in_cte_blocked():
    with pytest.raises(GuardrailError):
        validate_and_harden(
            "WITH t AS (DELETE FROM orders) SELECT * FROM t"
        )
