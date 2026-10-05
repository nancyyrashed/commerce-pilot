import pytest

from src.database_tools import (
    describe_table,
    list_tables,
    run_query,
    sample_rows,
)
from src.sql_validator import SQLValidationError


EXPECTED_TABLES = {
    "customers",
    "geolocation",
    "order_items",
    "order_payments",
    "order_reviews",
    "orders",
    "product_category_name_translation",
    "products",
    "sellers",
}


def test_list_tables_returns_expected_tables():
    """The reader should discover all nine CommercePilot tables."""

    tables = set(list_tables())

    assert tables == EXPECTED_TABLES


def test_describe_table_returns_orders_schema():
    """Schema inspection should expose the real orders columns."""

    columns = describe_table("orders")

    column_names = [
        column["column_name"]
        for column in columns
    ]

    assert "order_id" in column_names
    assert "customer_id" in column_names
    assert "order_status" in column_names
    assert "order_purchase_timestamp" in column_names


def test_describe_table_rejects_unknown_table():
    """Unknown tables should fail clearly."""

    with pytest.raises(ValueError):
        describe_table("does_not_exist")


def test_sample_rows_respects_requested_limit():
    """Sampling should return only the requested number of rows."""

    rows = sample_rows("orders", 2)

    assert len(rows) == 2


def test_sample_rows_rejects_large_limit():
    """Schema sampling is intentionally capped at 10 rows."""

    with pytest.raises(ValueError):
        sample_rows("orders", 50)


def test_sample_rows_rejects_unknown_table():
    """Sampling must not accept arbitrary table names."""

    with pytest.raises(ValueError):
        sample_rows("does_not_exist", 2)


def test_run_query_executes_safe_query():
    """A valid read-only query should execute successfully."""

    result = run_query(
        """
        SELECT order_status, COUNT(*) AS order_count
        FROM orders
        GROUP BY order_status
        ORDER BY order_count DESC;
        """
    )

    assert result["row_count"] > 0
    assert len(result["rows"]) == result["row_count"]
    assert "LIMIT 100" in result["sql"]


def test_run_query_enforces_row_limit():
    """An unbounded query should never return more than MAX_ROWS."""

    result = run_query(
        "SELECT order_id FROM orders;"
    )

    assert result["row_count"] == 100


def test_run_query_rejects_destructive_sql():
    """Unsafe SQL must be rejected before database execution."""

    with pytest.raises(SQLValidationError):
        run_query("DROP TABLE orders;")


def test_run_query_rejects_multiple_statements():
    """Multiple statements must never reach PostgreSQL."""

    with pytest.raises(SQLValidationError):
        run_query(
            "SELECT * FROM orders; DROP TABLE customers;"
        )