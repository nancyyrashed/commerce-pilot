import json
from pathlib import Path

from src.database_tools import run_query


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_FILE = PROJECT_ROOT / "evaluation" / "reference_queries.json"


def main():
    """
    Execute every hand-written reference query.

    This validates that our evaluation ground truth is syntactically
    valid, accepted by the SQL guardrails, and executable against the
    real CommercePilot PostgreSQL database.
    """

    with REFERENCE_FILE.open("r", encoding="utf-8") as file:
        reference_queries = json.load(file)

    passed = 0
    failed = []

    print(f"Validating {len(reference_queries)} reference queries...\n")

    for case_id, case in reference_queries.items():
        sql = case["sql"]

        try:
            result = run_query(sql)

            passed += 1

            print(
                f"[PASS] {case_id:<12} "
                f"rows={result['row_count']}"
            )

        except Exception as error:
            failed.append(
                {
                    "id": case_id,
                    "error": str(error),
                }
            )

            print(
                f"[FAIL] {case_id:<12} "
                f"{error}"
            )

    print("\nReference-query validation complete.")
    print(f"Passed: {passed}")
    print(f"Failed: {len(failed)}")

    if failed:
        print("\nFailures:")

        for failure in failed:
            print(
                f"- {failure['id']}: "
                f"{failure['error']}"
            )

        raise SystemExit(1)


if __name__ == "__main__":
    main()