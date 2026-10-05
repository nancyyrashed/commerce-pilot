import argparse
import json
from pathlib import Path
from pprint import pprint

from src.database_tools import run_query


PROJECT_ROOT = Path(__file__).resolve().parent.parent

REFERENCE_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "reference_queries.json"
)

RESULTS_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "answerable_results.json"
)


def main():
    parser = argparse.ArgumentParser(
        description="Inspect a failed evaluation case."
    )

    parser.add_argument(
        "case_id",
        help="Evaluation case ID, for example multi_08.",
    )

    args = parser.parse_args()

    with REFERENCE_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        references = json.load(file)

    with RESULTS_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        evaluation_results = json.load(file)

    result_record = next(
        (
            result
            for result in evaluation_results["results"]
            if result["id"] == args.case_id
        ),
        None,
    )

    if result_record is None:
        raise ValueError(
            f"{args.case_id} is not present in the current "
            "answerable_results.json file."
        )

    reference_sql = references[args.case_id]["sql"]
    generated_sql = result_record["generated_sql"]

    print("\nREFERENCE SQL:\n")
    print(reference_sql)

    print("\nREFERENCE RESULT:\n")
    reference_result = run_query(reference_sql)
    pprint(reference_result["rows"])

    print("\nGENERATED SQL:\n")
    print(generated_sql)

    print("\nGENERATED RESULT:\n")
    generated_result = run_query(generated_sql)
    pprint(generated_result["rows"])


if __name__ == "__main__":
    main()