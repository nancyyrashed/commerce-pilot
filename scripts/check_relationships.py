from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

# Map short table names to their CSV filenames.
FILES = {
    "customers": "olist_customers_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "categories": "product_category_name_translation.csv",
    "geolocation": "olist_geolocation_dataset.csv",
}


def read_column(table, column):
    # Read only the column needed for this check to reduce memory usage.
    df = pd.read_csv(
        RAW_DATA_DIR / FILES[table],
        usecols=[column],
        dtype="string",
        keep_default_na=False,
        na_values=[""],
    )
    return df[column]


def check_reference(source_table, source_column, target_table, target_column):
    source = read_column(source_table, source_column)
    target = read_column(target_table, target_column)

    # Missing source values are counted separately from unmatched values.
    missing = source.isna()

    # Find non-missing values that do not appear in the target column.
    unmatched = source.notna() & ~source.isin(target.dropna())

    print(
        f"\n{source_table}.{source_column}"
        f" -> {target_table}.{target_column}"
    )
    print(f"  Missing source values: {missing.sum():,}")
    print(f"  Unmatched source rows: {unmatched.sum():,}")
    print(f"  Distinct unmatched values: {source[unmatched].nunique():,}")

    if unmatched.any():
        examples = source[unmatched].drop_duplicates().head(5).tolist()
        print(f"  Examples: {examples}")


def main():
    # These relationships are candidates for database foreign keys.
    relationships = [
        ("orders", "customer_id", "customers", "customer_id"),
        ("order_items", "order_id", "orders", "order_id"),
        ("order_items", "product_id", "products", "product_id"),
        ("order_items", "seller_id", "sellers", "seller_id"),
        ("payments", "order_id", "orders", "order_id"),
        ("reviews", "order_id", "orders", "order_id"),
    ]

    print("CORE RELATIONSHIP CHECKS")
    for relationship in relationships:
        check_reference(*relationship)

    # Check lookup coverage separately: these may have incomplete matches.
    print("\nLOOKUP COVERAGE CHECKS")
    check_reference(
        "products", "product_category_name",
        "categories", "product_category_name",
    )

    # Postal prefixes are not unique in geolocation, so these are coverage
    # checks only, not proposed foreign keys to that column.
    for table in ["customers", "sellers"]:
        prefix_column = (
            "customer_zip_code_prefix"
            if table == "customers"
            else "seller_zip_code_prefix"
        )
        check_reference(
            table, prefix_column,
            "geolocation", "geolocation_zip_code_prefix",
        )


if __name__ == "__main__":
    main()