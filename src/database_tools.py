import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql
from psycopg.rows import dict_row

from src.sql_validator import MAX_ROWS, validate_sql


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def get_reader_connection():
    """
    Open a PostgreSQL connection using only the restricted
    CommercePilot reader account.

    The future production DATABASE_URL must also belong to
    the read-only database role.
    """

    database_url = os.getenv("DATABASE_URL")

    # Production will use the Neon connection string.
    if database_url:
        return psycopg.connect(
            database_url,
            connect_timeout=10,
            row_factory=dict_row,
        )

    # Local development uses PostgreSQL running through Docker.
    return psycopg.connect(
        host="127.0.0.1",
        port=int(os.environ["POSTGRES_PORT"]),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_READONLY_USER"],
        password=os.environ["POSTGRES_READONLY_PASSWORD"],
        connect_timeout=10,
        row_factory=dict_row,
    )


def list_tables():
    """Return the names of the project's public PostgreSQL tables."""

    query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """

    with get_reader_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)

            return [row["table_name"] for row in cursor.fetchall()]


def describe_table(table_name):
    """
    Return column information for one public table.

    The table must exist in the public schema.
    """

    query = """
        SELECT
            column_name,
            data_type,
            is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position
    """

    with get_reader_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (table_name,))
            columns = cursor.fetchall()

    if not columns:
        raise ValueError(
            f"Table '{table_name}' does not exist in the public schema."
        )

    return columns


def sample_rows(table_name, limit=5):
    """
    Return a small sample from a public table.

    This function is intentionally capped because it is used only
    to help the future agent understand the table's contents.
    """

    if not isinstance(limit, int) or isinstance(limit, bool):
        raise TypeError("limit must be an integer.")

    if limit < 1 or limit > 10:
        raise ValueError("limit must be between 1 and 10.")

    # Validate the requested table against the real schema first.
    if table_name not in list_tables():
        raise ValueError(
            f"Table '{table_name}' does not exist in the public schema."
        )

    query = sql.SQL("SELECT * FROM {} LIMIT %s").format(
        sql.Identifier("public", table_name)
    )

    with get_reader_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (limit,))
            return cursor.fetchall()


def run_query(sql_text, max_rows=MAX_ROWS):
    """
    Validate and execute a read-only SQL query.

    Model-generated SQL must enter PostgreSQL through this function.
    The validator runs before database execution.
    """

    # Parse and rewrite the SQL before it reaches PostgreSQL.
    safe_sql = validate_sql(
        sql_text,
        max_rows=max_rows,
    )

    with get_reader_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(safe_sql)
            rows = cursor.fetchall()

    return {
        "sql": safe_sql,
        "rows": rows,
        "row_count": len(rows),
    }