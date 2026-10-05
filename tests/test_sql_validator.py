import pytest

from src.sql_validator import (
    MAX_ROWS,
    SQLValidationError,
    validate_sql,
)


def test_adds_default_row_limit():
    """Queries without LIMIT should receive CommercePilot's hard cap."""

    safe_sql = validate_sql(
        "SELECT order_id, order_status FROM orders;"
    )

    assert f"LIMIT {MAX_ROWS}" in safe_sql


def test_preserves_smaller_limit():
    """A limit below the maximum should remain unchanged."""

    safe_sql = validate_sql(
        "SELECT order_id FROM orders LIMIT 5;"
    )

    assert "LIMIT 5" in safe_sql


def test_reduces_large_limit():
    """A model-requested limit above the cap should be reduced."""

    safe_sql = validate_sql(
        "SELECT order_id FROM orders LIMIT 1000;"
    )

    assert f"LIMIT {MAX_ROWS}" in safe_sql
    assert "LIMIT 1000" not in safe_sql


def test_rejects_drop():
    """Destructive DDL must never be accepted."""

    with pytest.raises(SQLValidationError):
        validate_sql("DROP TABLE orders;")


def test_rejects_delete():
    """DELETE is not a read-only query."""

    with pytest.raises(SQLValidationError):
        validate_sql("DELETE FROM orders;")


def test_rejects_update():
    """UPDATE is not a read-only query."""

    with pytest.raises(SQLValidationError):
        validate_sql(
            "UPDATE orders SET order_status = 'canceled';"
        )


def test_rejects_insert():
    """INSERT is not a read-only query."""

    with pytest.raises(SQLValidationError):
        validate_sql(
            """
            INSERT INTO orders (order_id)
            VALUES ('unsafe');
            """
        )


def test_rejects_multiple_statements():
    """Only one SQL statement may be submitted at a time."""

    with pytest.raises(SQLValidationError):
        validate_sql(
            "SELECT * FROM orders; DROP TABLE customers;"
        )


def test_rejects_select_into():
    """
    PostgreSQL SELECT INTO creates a table even though
    the statement begins with SELECT.
    """

    with pytest.raises(SQLValidationError):
        validate_sql(
            "SELECT * INTO copied_orders FROM orders;"
        )


def test_rejects_empty_query():
    """Empty SQL must not reach PostgreSQL."""

    with pytest.raises(SQLValidationError):
        validate_sql("")


def test_accepts_cte_select():
    """Read-only SELECT queries using a CTE should be accepted."""

    safe_sql = validate_sql(
        """
        WITH delivered_orders AS (
            SELECT order_id
            FROM orders
            WHERE order_status = 'delivered'
        )
        SELECT order_id
        FROM delivered_orders;
        """
    )

    assert "WITH delivered_orders AS" in safe_sql
    assert f"LIMIT {MAX_ROWS}" in safe_sql


def test_rejects_invalid_max_rows():
    """The configured result cap must be a positive integer."""

    with pytest.raises(ValueError):
        validate_sql(
            "SELECT * FROM orders;",
            max_rows=0,
        )


def test_rejects_data_modifying_cte():
    """A SELECT must not hide a write operation inside a CTE."""

    with pytest.raises(SQLValidationError):
        validate_sql(
            """
            WITH deleted AS (
                DELETE FROM orders
                RETURNING order_id
            )
            SELECT * FROM deleted;
            """
        )


def test_rejects_locking_select():
    """Read queries must not acquire row locks."""

    with pytest.raises(SQLValidationError):
        validate_sql(
            "SELECT * FROM orders FOR UPDATE;"
        )