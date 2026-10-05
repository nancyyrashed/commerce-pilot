import argparse
import json
import time
from pathlib import Path

from src.agent_nodes import classify_request_node


PROJECT_ROOT = Path(__file__).resolve().parent.parent

QUESTIONS_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "eval_questions.json"
)

RESULTS_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "classification_results.json"
)

DEFAULT_CASE_DELAY_SECONDS = 3.0
DEFAULT_PROVIDER_RETRIES = 3
DEFAULT_PROVIDER_RETRY_DELAY_SECONDS = 3.0


def is_provider_error(error):
    """
    Identify temporary LLM-provider or network failures.

    Infrastructure failures should be retried and excluded from
    classification accuracy if they still cannot be completed.
    """

    error_name = type(error).__name__.lower()
    message = str(error).lower()

    provider_error_names = (
        "apiconnectionerror",
        "ratelimiterror",
        "apitimeouterror",
        "connecterror",
        "readtimeout",
        "connecttimeout",
    )

    provider_error_messages = (
        "connection error",
        "rate limit",
        "429",
        "timed out",
        "timeout",
        "temporarily unavailable",
        "service unavailable",
        "server disconnected",
    )

    return (
        any(
            name in error_name
            for name in provider_error_names
        )
        or any(
            marker in message
            for marker in provider_error_messages
        )
    )


def classify_with_provider_retry(
    question,
    provider_retries,
    retry_delay,
):
    """
    Run the classifier with retries for temporary provider failures.
    """

    for provider_attempt in range(
        provider_retries + 1
    ):
        try:
            return classify_request_node(
                {
                    "question": question,
                }
            )

        except Exception as error:
            if not is_provider_error(error):
                raise

            if provider_attempt >= provider_retries:
                raise

            retry_number = provider_attempt + 1

            print(
                "  Temporary provider error. "
                f"Retrying ({retry_number}/{provider_retries})..."
            )

            time.sleep(
                retry_delay * retry_number
            )


def load_cases():
    """
    Load the 15 cases that should not proceed to SQL generation.
    """

    with QUESTIONS_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        questions = json.load(file)

    return [
        case
        for case in questions
        if case["expected_behavior"]
        in {
            "clarify",
            "unanswerable",
            "reject",
        }
    ]


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate CommercePilot request classification."
        )
    )

    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Skip the first N classification cases.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Evaluate only the first N remaining cases.",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_CASE_DELAY_SECONDS,
        help="Seconds to wait between classification cases.",
    )

    parser.add_argument(
        "--provider-retries",
        type=int,
        default=DEFAULT_PROVIDER_RETRIES,
        help=(
            "Number of retries for temporary provider "
            "or network failures."
        ),
    )

    parser.add_argument(
        "--retry-delay",
        type=float,
        default=DEFAULT_PROVIDER_RETRY_DELAY_SECONDS,
        help=(
            "Base delay in seconds between provider retries."
        ),
    )

    args = parser.parse_args()

    cases = load_cases()

    cases = cases[args.start:]

    if args.limit is not None:
        cases = cases[: args.limit]

    results = []

    passed = 0
    failed = 0
    infrastructure_errors = 0

    print(
        f"Evaluating {len(cases)} classification cases...\n"
    )

    for index, case in enumerate(
        cases,
        start=1,
    ):
        case_id = case["id"]
        question = case["question"]
        expected_type = case["expected_behavior"]

        print(
            f"[{index}/{len(cases)}] "
            f"{case_id}: {question}"
        )

        try:
            classification = (
                classify_with_provider_retry(
                    question=question,
                    provider_retries=args.provider_retries,
                    retry_delay=args.retry_delay,
                )
            )

            actual_type = classification[
                "request_type"
            ]

            direct_response = classification[
                "direct_response"
            ]

            correct = (
                actual_type == expected_type
            )

            # Every non-answerable route should include a response
            # explaining the limitation, rejection, or clarification.
            has_direct_response = bool(
                direct_response.strip()
            )

            correct = (
                correct
                and has_direct_response
            )

            result_record = {
                "id": case_id,
                "category": case["category"],
                "question": question,
                "expected_type": expected_type,
                "actual_type": actual_type,
                "correct": correct,
                "scored": True,
                "infrastructure_error": False,
                "direct_response": direct_response,
                "sql_generated": False,
                "error": None,
            }

            if correct:
                passed += 1
                print("  PASS")

            else:
                failed += 1
                print("  FAIL")

                print(
                    f"  Expected: {expected_type}"
                )

                print(
                    f"  Actual:   {actual_type}"
                )

        except Exception as error:
            infrastructure_error = (
                is_provider_error(error)
            )

            if infrastructure_error:
                infrastructure_errors += 1

                print(
                    "  INFRASTRUCTURE ERROR "
                    "(excluded from accuracy)"
                )

            else:
                failed += 1
                print("  FAIL")

            print(
                f"  Error: {error}"
            )

            result_record = {
                "id": case_id,
                "category": case["category"],
                "question": question,
                "expected_type": expected_type,
                "actual_type": None,
                "correct": False,
                "scored": not infrastructure_error,
                "infrastructure_error": infrastructure_error,
                "direct_response": "",
                "sql_generated": False,
                "error": str(error),
            }

        results.append(result_record)

        print(
            f"  Response: "
            f"{result_record['direct_response']}\n"
        )

        if (
            index < len(cases)
            and args.delay > 0
        ):
            time.sleep(args.delay)

    scored_cases = passed + failed

    accuracy = (
        passed / scored_cases
        if scored_cases
        else 0.0
    )

    output = {
        "summary": {
            "total_cases": len(cases),
            "scored_cases": scored_cases,
            "passed": passed,
            "failed": failed,
            "infrastructure_errors": infrastructure_errors,
            "classification_accuracy": accuracy,
        },
        "results": results,
    }

    with RESULTS_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print("Classification evaluation complete.")
    print(f"Total cases: {len(cases)}")
    print(f"Scored cases: {scored_cases}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(
        "Infrastructure errors: "
        f"{infrastructure_errors}"
    )

    if scored_cases:
        print(
            f"Classification accuracy: "
            f"{accuracy:.2%}"
        )

    else:
        print(
            "Classification accuracy: "
            "not available"
        )

    print(
        f"Results saved to: {RESULTS_FILE}"
    )


if __name__ == "__main__":
    main()