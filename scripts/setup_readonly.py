import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql
from psycopg.errors import InsufficientPrivilege


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

TABLES = [
    "customers",
    "sellers",
    "product_category_name_translation",
    "products",
    "orders",
    "order_items",
    "order_payments",
    "order_reviews",
    "geolocation",
]

# Stop unexpectedly expensive agent queries from running indefinitely.
STATEMENT_TIMEOUT = "10s"


def create_reader(connection_settings, reader_name, reader_password):
    """Use the administrator account to create a restricted reader."""

    role = sql.Identifier(reader_name)
    database = sql.Identifier(connection_settings["dbname"])

    with psycopg.connect(
        **connection_settings,
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    ) as connection:
        with connection.cursor() as cursor:
            # Avoid changing an existing account unexpectedly.
            cursor.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s",
                (reader_name,),
            )
            if cursor.fetchone() is not None:
                raise RuntimeError(
                    f"Role '{reader_name}' already exists. "
                    "No account changes were made."
                )

            # Create a login account with no administrative capabilities.
            # Identifier and Literal safely quote the name and password.
            cursor.execute(
                sql.SQL(
                    """
                    CREATE ROLE {}
                    WITH LOGIN
                         NOSUPERUSER
                         NOCREATEDB
                         NOCREATEROLE
                         NOINHERIT
                         NOREPLICATION
                         NOBYPASSRLS
                         PASSWORD {}
                    """
                ).format(role, sql.Literal(reader_password))
            )

            # PUBLIC means all accounts, including newly created ones.
            # Remove shared permissions to create schemas or temp tables.
            cursor.execute(
                sql.SQL(
                    "REVOKE CREATE, TEMPORARY ON DATABASE {} FROM PUBLIC"
                ).format(database)
            )

            # Also prevent accounts from creating tables in public
            # merely through permissions granted to everyone.
            cursor.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")

            cursor.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    database, role
                )
            )
            cursor.execute(
                sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role)
            )

            # Grant read access only to our specified data tables.
            # Future tables, such as application logs, are not included.
            for table_name in TABLES:
                cursor.execute(
                    sql.SQL("GRANT SELECT ON TABLE {} TO {}").format(
                        sql.Identifier("public", table_name),
                        role,
                    )
                )

            # Apply a database-level safeguard to every statement
            # executed by the analytics reader.
            cursor.execute(
                sql.SQL(
                    "ALTER ROLE {} SET statement_timeout = {}"
                ).format(
                    role,
                    sql.Literal(STATEMENT_TIMEOUT),
                )
            )

    # The administrator transaction has now committed.
    print(f"Created reader account: {reader_name}")
    print(f"Statement timeout: {STATEMENT_TIMEOUT}")


def expect_denied(connection, label, statement):
    """Check that PostgreSQL rejects an operation."""

    try:
        # Each test has its own transaction.
        # Both a permission error and an unexpected success cause rollback.
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(statement)

                # If execution reached here, the operation was allowed.
                # Raising an error rolls back any changes before stopping.
                raise RuntimeError(
                    f"FAILED: {label} was unexpectedly allowed. "
                    "The test transaction was rolled back."
                )

    except InsufficientPrivilege:
        # This is the specific error we expect from permission enforcement.
        print(f"PASS: {label} blocked by database permissions")


def verify_reader(connection_settings, reader_name, reader_password):
    """Connect as the reader and test its actual permissions."""

    with psycopg.connect(
        **connection_settings,
        user=reader_name,
        password=reader_password,
        autocommit=True,
    ) as connection:
        # Verify that the reader can query all nine tables.
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user")
            print(f"\nTesting as: {cursor.fetchone()[0]}")

            # Confirm that the role received the expected query timeout.
            cursor.execute("SHOW statement_timeout")
            actual_timeout = cursor.fetchone()[0]

            if actual_timeout != STATEMENT_TIMEOUT:
                raise RuntimeError(
                    "FAILED: unexpected statement timeout. "
                    f"Expected {STATEMENT_TIMEOUT}, got {actual_timeout}."
                )

            print(
                "PASS: statement_timeout "
                f"is configured as {actual_timeout}"
            )

            for table_name in TABLES:
                cursor.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}").format(
                        sql.Identifier("public", table_name)
                    )
                )
                count = cursor.fetchone()[0]
                print(f"PASS: SELECT {table_name} ({count:,} rows)")

        # WHERE FALSE makes these tests affect zero rows even if
        # write permissions were accidentally granted.
        write_tests = [
            (
                "INSERT",
                """
                INSERT INTO public.orders
                SELECT * FROM public.orders WHERE FALSE
                """,
            ),
            (
                "UPDATE",
                """
                UPDATE public.orders
                SET order_status = order_status
                WHERE FALSE
                """,
            ),
            (
                "DELETE",
                "DELETE FROM public.orders WHERE FALSE",
            ),
            (
                "CREATE TABLE",
                """
                CREATE TABLE public.commercepilot_permission_probe (
                    id INTEGER
                )
                """,
            ),
            (
                "CREATE TEMP TABLE",
                """
                CREATE TEMP TABLE commercepilot_temp_probe (
                    id INTEGER
                )
                """,
            ),
        ]

        for label, statement in write_tests:
            expect_denied(connection, label, statement)

    print("\nSuccess: reader access and permission checks passed.")


def main():
    reader_name = os.environ["POSTGRES_READONLY_USER"]
    reader_password = os.environ["POSTGRES_READONLY_PASSWORD"]

    if not reader_name.strip() or not reader_password:
        raise ValueError("Reader username and password must not be empty.")

    if reader_name == os.environ["POSTGRES_USER"]:
        raise ValueError(
            "Reader and administrator must be different accounts."
        )

    connection_settings = {
        "host": "127.0.0.1",
        "port": int(os.environ["POSTGRES_PORT"]),
        "dbname": os.environ["POSTGRES_DB"],
        "connect_timeout": 10,
    }

    create_reader(
        connection_settings,
        reader_name,
        reader_password,
    )
    verify_reader(
        connection_settings,
        reader_name,
        reader_password,
    )


if __name__ == "__main__":
    main()