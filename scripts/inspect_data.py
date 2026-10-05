from pathlib import Path

import pandas as pd


# Locate the original CSV files inside the project.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"


def main():
    # Find CSV files and inspect them in alphabetical order.
    csv_files = sorted(RAW_DATA_DIR.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {RAW_DATA_DIR}")

    print(f"Found {len(csv_files)} CSV files.")

    for csv_path in csv_files:
        # Read values as text for this initial inspection.
        # This preserves leading zeros in identifiers and postal codes.
        # Treat empty fields as missing, without interpreting text
        # such as "NA" or "NULL" as missing automatically.
        df = pd.read_csv(
            csv_path,
            dtype="string",
            keep_default_na=False,
            na_values=[""],
        )

        print("\n" + "=" * 60)
        print(f"File: {csv_path.name}")
        print(f"Rows: {len(df):,}")
        print(f"Columns: {len(df.columns)}")

        # Count repeated rows after the first occurrence.
        # A duplicate here means ALL column values match.
        print(f"Exact duplicate rows: {df.duplicated().sum():,}")

        print("\nColumn names:")
        print(", ".join(df.columns))

        # Count missing values separately for each column.
        missing_counts = df.isna().sum()

        # Display only columns containing at least one missing value.
        missing_counts = missing_counts[missing_counts > 0]

        print("\nMissing values:")
        if missing_counts.empty:
            print("None")
        else:
            print(missing_counts.to_string())


if __name__ == "__main__":
    main()