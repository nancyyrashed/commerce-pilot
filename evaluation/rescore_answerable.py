import json
from pathlib import Path

from evaluation.evaluate_answerable import (
    load_reference_queries,
    results_match,
)
from src.database_tools import run_query


PROJECT_ROOT = Path(__file__).resolve().parent.parent

EVAL_QUESTIONS_FILE = (
    PROJECT_ROOT / "evaluation" / "eval_questions.json"
)

RESULTS_FILE = (
    PROJECT_ROOT / "evaluation" / "answerable_results.json"
)

RESCORED_RESULTS_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "answerable_rescored_results.json"
)


def load_eval_cases():
    """
    Load evaluation cases indexed by case ID.
    """

    with EVAL_QUESTIONS_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if isinstance(data, dict):
        cases = data.get(
            "cases",
            data.get("questions", []),
        )
    else:
        cases = data

    return {
        case["id"]: case
        for case in cases
    }


def load_saved_results():
    """
    Load the most recent answerable evaluation results.
    """

    with RESULTS_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    return data["results"]


def main():
    """
    Re-score previously generated SQL without calling the LLM again.

    This applies the corrected semantic comparison rules to the
    already-generated SQL and saves the corrected benchmark separately
    from the original raw evaluation run.
    """

    eval_cases = load_eval_cases()
    references = load_reference_queries()
    saved_results = load_saved_results()

    total = 0
    passed = 0
    failed = 0

    rescored_results = []

    print(
        f"Re-scoring {len(saved_results)} "
        f"saved answerable cases...\n"
    )

    for result in saved_results:
        case_id = result["id"]

        case = eval_cases[case_id]

        generated_sql = result.get(
            "generated_sql"
        )

        rescored_entry = dict(result)

        if not generated_sql:
            total += 1
            failed += 1

            rescored_entry[
                "correct"
            ] = False

            rescored_entry[
                "rescored_reason"
            ] = "No generated SQL saved."

            rescored_results.append(
                rescored_entry
            )

            print(
                f"{case_id}: FAIL "
                f"(No generated SQL saved.)"
            )

            continue

        reference_sql = references[case_id]

        reference_result = run_query(
            reference_sql
        )

        generated_result = run_query(
            generated_sql
        )

        reference_rows = (
            reference_result["rows"]
        )

        generated_rows = (
            generated_result["rows"]
        )

        result_values_match = (
            results_match(
                reference_rows,
                generated_rows,
            )
        )

        expected_tables = set(
            case.get(
                "expected_tables",
                [],
            )
        )

        actual_tables = set(
            result.get(
                "tables_used",
                [],
            )
        )

        expected_tables_used = (
            expected_tables
            <= actual_tables
        )

        correct = (
            result_values_match
            and expected_tables_used
        )

        total += 1

        rescored_entry[
            "correct"
        ] = correct

        rescored_entry[
            "expected_tables"
        ] = sorted(
            expected_tables
        )

        rescored_entry[
            "expected_tables_used"
        ] = expected_tables_used

        rescored_entry[
            "reference_row_count"
        ] = len(
            reference_rows
        )

        rescored_entry[
            "generated_row_count"
        ] = len(
            generated_rows
        )

        rescored_entry[
            "result_values_match"
        ] = result_values_match

        reasons = []

        if not result_values_match:
            reasons.append(
                "result values differ"
            )

        if not expected_tables_used:
            missing_tables = sorted(
                expected_tables
                - actual_tables
            )

            reasons.append(
                "missing expected tables: "
                + ", ".join(
                    missing_tables
                )
            )

        if correct:
            passed += 1

            rescored_entry[
                "rescored_reason"
            ] = None

            print(
                f"{case_id}: PASS"
            )

        else:
            failed += 1

            reason_text = "; ".join(
                reasons
            )

            rescored_entry[
                "rescored_reason"
            ] = reason_text

            print(
                f"{case_id}: FAIL "
                f"({reason_text})"
            )

        rescored_results.append(
            rescored_entry
        )

    accuracy = (
        passed / total
        if total
        else 0.0
    )

    output = {
        "summary": {
            "total_cases": total,
            "scored_cases": total,
            "passed": passed,
            "failed": failed,
            "infrastructure_errors": 0,
            "execution_accuracy": accuracy,
        },
        "results": rescored_results,
    }

    with RESCORED_RESULTS_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    print(
        "\nRe-score complete."
    )

    print(
        f"Total cases: {total}"
    )

    print(
        f"Passed: {passed}"
    )

    print(
        f"Failed: {failed}"
    )

    print(
        "Execution accuracy: "
        f"{accuracy * 100:.2f}%"
    )

    print(
        "Results saved to: "
        f"{RESCORED_RESULTS_FILE}"
    )


if __name__ == "__main__":
    main()