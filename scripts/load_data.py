import math
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv
from psycopg import sql


# Locate project files independently of the terminal's working directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
SCHEMA_FILE = PROJECT_ROOT / "scripts" / "schema.sql"

load_dotenv(PROJECT_ROOT / ".env")


# Load parent tables before tables that reference them.
TABLES = [
    ("customers", "olist_customers_dataset.csv"),
    ("sellers", "olist_sellers_dataset.csv"),
    (
        "product_category_name_translation",
        "product_category_name_translation.csv",
    ),
    ("products", "olist_products_dataset.csv"),
    ("orders", "olist_orders_dataset.csv"),
    ("order_items", "olist_order_items_dataset.csv"),
    ("order_payments", "olist_order_payments_dataset.csv"),
    ("order_reviews", "olist_order_reviews_dataset.csv"),
    ("geolocation", "olist_geolocation_dataset.csv"),
]


def convert_value(value, data_type):
    """Convert a CSV value to the Python type needed by PostgreSQL."""

    # Psycopg writes Python None as SQL NULL.
    if pd.isna(value):
        return None

    if data_type == "text":
        return value

    if data_type == "integer":
        # Some whole-number fields appear as strings such as "10.0".
        number = Decimal(value)

        # Reject fractional or non-finite values instead of truncating.
        if not number.is_finite() or number != number.to_integral_value():
            raise ValueError("Expected a finite whole number.")

        return int(number)

    if data_type == "numeric":
        # Decimal preserves exact amounts without binary float rounding.
        number = Decimal(value)

        if not number.is_finite():
            raise ValueError("Expected a finite monetary amount.")

        # Our monetary columns allow two decimal places.
        # Reject extra precision instead of silently rounding it.
        if number != number.quantize(Decimal("0.01")):
            raise ValueError("Monetary amount has more than two decimals.")

        return number

    if data_type == "double precision":
        number = float(value)

        if not math.isfinite(number):
            raise ValueError("Expected a finite coordinate.")

        return number

    if data_type == "timestamp without time zone":
        # Parse the source date format without assigning a timezone.
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")

    raise ValueError(f"Unsupported database type: {data_type}")


def load_table(cursor, table_name, filename):
    """Read, prepare, load and count one table."""

    print(f"\nLoading {table_name}...", flush=True)

    # Initially read everything as text to preserve source identifiers.
    df = pd.read_csv(
        RAW_DATA_DIR / filename,
        dtype="string",
        keep_default_na=False,
        na_values=[""],
    )

    source_count = len(df)

    # Only geolocation has exact duplicate rows in our inspection.
    if table_name == "geolocation":
        df = df.drop_duplicates()
        print(f"  Exact duplicates removed: {source_count - len(df):,}")

    # Ask PostgreSQL for column names and types from our schema.
    # Exclude the generated geolocation_id: PostgreSQL supplies it.
    cursor.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND is_identity = 'NO'
        ORDER BY ordinal_position
        """,
        (table_name,),
    )
    column_details = cursor.fetchall()
    column_names = [column for column, data_type in column_details]

    # Stop if the source columns differ from the schema we designed.
    if set(df.columns) != set(column_names):
        missing = sorted(set(column_names) - set(df.columns))
        extra = sorted(set(df.columns) - set(column_names))
        raise ValueError(
            f"{filename}: column mismatch. Missing: {missing}; extra: {extra}"
        )

    # Arrange CSV values in the same order as the database columns.
    df = df[column_names]

    # Safely quote table and column names when building SQL.
    copy_command = sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier("public", table_name),
        sql.SQL(", ").join(sql.Identifier(name) for name in column_names),
    )

    # COPY streams rows into PostgreSQL efficiently.
    with cursor.copy(copy_command) as copy:
        for row_number, row in enumerate(
            df.itertuples(index=False, name=None),
            start=1,
        ):
            converted_row = []

            for (column_name, data_type), value in zip(column_details, row):
                try:
                    converted_row.append(convert_value(value, data_type))
                except (ValueError, ArithmeticError) as error:
                    raise ValueError(
                        f"{table_name}: conversion failed at cleaned row "
                        f"{row_number}, column '{column_name}'."
                    ) from error

            copy.write_row(converted_row)

    # Confirm that every prepared row reached the database.
    cursor.execute(
        sql.SQL("SELECT COUNT(*) FROM {}").format(
            sql.Identifier("public", table_name)
        )
    )
    loaded_count = cursor.fetchone()[0]

    if loaded_count != len(df):
        raise RuntimeError(f"Row count mismatch for {table_name}.")

    print(f"  Source rows: {source_count:,}")
    print(f"  Loaded rows: {loaded_count:,}")


def main():
    # Check required input files before making database changes.
    required_files = [SCHEMA_FILE]
    required_files.extend(RAW_DATA_DIR / filename for _, filename in TABLES)

    for path in required_files:
        if not path.is_file():
            raise FileNotFoundError(f"Required file not found: {path}")

    # All database work below belongs to one transaction.
    # Successful exit commits it; an exception rolls it back.
    with psycopg.connect(
        host="127.0.0.1",
        port=int(os.environ["POSTGRES_PORT"]),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=10,
    ) as connection:
        with connection.cursor() as cursor:
            # Ensure the schema file creates tables in public.
            cursor.execute("SET LOCAL search_path TO public")

            # This initial loader creates a fresh dataset.
            # Refuse to overwrite or append to existing project tables.
            for table_name, _ in TABLES:
                cursor.execute(
                    "SELECT to_regclass(%s)",
                    (f"public.{table_name}",),
                )
                if cursor.fetchone()[0] is not None:
                    raise RuntimeError(
                        f"Table '{table_name}' already exists. "
                        "Load stopped without changing existing data."
                    )

            # Execute the table definitions saved in the previous step.
            print("Creating database tables...", flush=True)
            cursor.execute(
                SCHEMA_FILE.read_text(encoding="utf-8-sig"),
                prepare=False,
            )

            for table_name, filename in TABLES:
                load_table(cursor, table_name, filename)

    # This prints only after the transaction has committed successfully.
    print("\nSuccess: all nine tables were loaded and committed.")


if __name__ == "__main__":
    main()