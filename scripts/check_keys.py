from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"


def read_csv(filename):
    # Preserve identifiers and recognize empty fields as missing.
    return pd.read_csv(
        RAW_DATA_DIR / filename,
        dtype="string",
        keep_default_na=False,
        na_values=[""],
    )


def check_key(df, columns):
    # Count rows with any missing part of the proposed key.
    missing_rows = df[columns].isna().any(axis=1).sum()

    # Compare only the proposed key columns, not the entire row.
    duplicate_rows = df.duplicated(subset=columns).sum()

    print(f"  Key: {', '.join(columns)}")
    print(f"  Rows with missing key values: {missing_rows:,}")
    print(f"  Duplicate key rows beyond the first: {duplicate_rows:,}")


def main():
    # These are possible keys to verify, not assumptions to enforce yet.
    candidates = [
        ("olist_customers_dataset.csv", ["customer_id"]),
        ("olist_orders_dataset.csv", ["order_id"]),
        ("olist_products_dataset.csv", ["product_id"]),
        ("olist_sellers_dataset.csv", ["seller_id"]),
        ("olist_order_items_dataset.csv", ["order_id", "order_item_id"]),
        (
            "olist_order_payments_dataset.csv",
            ["order_id", "payment_sequential"],
        ),
        ("olist_order_reviews_dataset.csv", ["review_id"]),
        (
            "olist_order_reviews_dataset.csv",
            ["review_id", "order_id"],
        ),
        (
            "product_category_name_translation.csv",
            ["product_category_name"],
        ),
    ]

    for filename, columns in candidates:
        print(f"\n{filename}")
        df = read_csv(filename)
        check_key(df, columns)

    # Compare customer records with distinct customer identities.
    customers = read_csv("olist_customers_dataset.csv")
    print("\nCustomer identities:")
    print(f"  Customer rows: {len(customers):,}")
    print(
        "  Distinct customer_unique_id values: "
        f"{customers['customer_unique_id'].nunique():,}"
    )

    # Check whether postal prefixes remain repeated after exact deduplication.
    # This changes only the in-memory table, not the original CSV.
    geo = read_csv("olist_geolocation_dataset.csv").drop_duplicates()
    print("\nGeolocation after removing exact duplicate rows:")
    print(f"  Remaining rows: {len(geo):,}")
    print(
        "  Distinct postal prefixes: "
        f"{geo['geolocation_zip_code_prefix'].nunique():,}"
    )
    check_key(geo, ["geolocation_zip_code_prefix"])


if __name__ == "__main__":
    main()