import argparse
import json
import time
from pathlib import Path

from src.agent_graph import MAX_ATTEMPTS
from src.agent_nodes import (
    classify_and_generate_sql_node,
    execute_sql_node,
    generate_sql_node,
    inspect_schema_node,
)
from src.database_tools import run_query

from evaluation.evaluate_answerable import (
    is_provider_error,
    load_reference_queries,
    results_match,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

QUESTIONS_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "eval_questions.json"
)

DEFAULT_RESULTS_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "production_regression_results.json"
)

DEFAULT_CASE_DELAY_SECONDS = 8.0
DEFAULT_PROVIDER_RETRIES = 3
DEFAULT_PROVIDER_RETRY_DELAY_SECONDS = 3.0


def load_cases():
    """
    Load the complete 60-case CommercePilot evaluation suite.

    The suite contains:
    - 45 answerable text-to-SQL cases
    - 15 clarify/unanswerable/reject cases
    """

    with QUESTIONS_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def expected_request_type(
    case,
):
    """
    Convert the evaluation-suite behavior label into the request
    type returned by the optimized planner.

    The historical benchmark uses "answer" while the agent uses
    "answerable".
    """

    expected_behavior = case[
        "expected_behavior"
    ]

    if expected_behavior == "answer":
        return "answerable"

    return expected_behavior


def build_initial_state(
    question,
    schema_context,
):
    """
    Build the state supplied to the optimized production planner.
    """

    return {
        "question": question,
        "request_type": "",
        "direct_response": "",
        "schema_context": schema_context,
        "sql": "",
        "query_result": [],
        "tables_used": [],
        "attempts": 0,
        "last_error": None,
        "answer": "",
    }


def inspect_schema_once():
    """
    Build the live database schema once.

    inspect_schema_node itself now has an in-process cache, but the
    evaluator also explicitly reuses the returned context so every
    benchmark case receives identical schema information.
    """

    state = build_initial_state(
        question="",
        schema_context="",
    )

    update = inspect_schema_node(
        state
    )

    return update[
        "schema_context"
    ]


def call_with_provider_retry(
    function,
    state,
    provider_retries,
    retry_delay,
):
    """
    Execute an LLM-backed agent node with retries for temporary
    provider/network failures.

    Provider failures are infrastructure events and must not be
    counted as model-accuracy failures.
    """

    for provider_attempt in range(
        provider_retries + 1
    ):

        try:
            return function(
                state
            )

        except Exception as error:
            if not is_provider_error(
                error
            ):
                raise

            if (
                provider_attempt
                >= provider_retries
            ):
                raise

            retry_number = (
                provider_attempt + 1
            )

            print(
                "  Temporary provider error. "
                f"Retrying "
                f"({retry_number}/"
                f"{provider_retries})..."
            )

            time.sleep(
                retry_delay
                * retry_number
            )


def plan_request(
    state,
    provider_retries,
    retry_delay,
):
    """
    Run CommercePilot's optimized first-stage production planner.

    This is the architecture now used by the application:
    classification and initial SQL generation happen in one LLM call.
    """

    return call_with_provider_retry(
        function=(
            classify_and_generate_sql_node
        ),
        state=state,
        provider_retries=provider_retries,
        retry_delay=retry_delay,
    )


def repair_sql(
    state,
    provider_retries,
    retry_delay,
):
    """
    Run the existing SQL repair node after a failed execution.

    This mirrors the production LangGraph retry route.
    """

    return call_with_provider_retry(
        function=generate_sql_node,
        state=state,
        provider_retries=provider_retries,
        retry_delay=retry_delay,
    )


def execute_answerable_plan(
    state,
    provider_retries,
    retry_delay,
):
    """
    Execute the SQL produced by the combined planner.

    If SQL validation or database execution fails, follow the same
    bounded repair loop used by the production graph.
    """

    while (
        state.get(
            "attempts",
            0,
        )
        <= MAX_ATTEMPTS
    ):

        execution_update = (
            execute_sql_node(
                state
            )
        )

        state.update(
            execution_update
        )

        if not state.get(
            "last_error"
        ):
            break

        if (
            state.get(
                "attempts",
                0,
            )
            >= MAX_ATTEMPTS
        ):
            break

        repair_update = (
            repair_sql(
                state=state,
                provider_retries=(
                    provider_retries
                ),
                retry_delay=(
                    retry_delay
                ),
            )
        )

        state.update(
            repair_update
        )

    return state


def evaluate_answerable_case(
    case,
    state,
    references,
    provider_retries,
    retry_delay,
):
    """
    Score one answerable case.

    Correctness requires:

    - planner classification = answerable
    - SQL is present
    - SQL executes successfully
    - required tables are used
    - generated result matches the hand-written reference result
    """

    case_id = case["id"]

    expected_tables = (
        case.get(
            "expected_tables",
            [],
        )
    )

    generated_sql = (
        state.get(
            "sql",
            "",
        )
        or ""
    )

    if not generated_sql.strip():
        return {
            "correct": False,
            "execution_succeeded": False,
            "expected_tables_used": False,
            "result_values_match": False,
            "reference_row_count": 0,
            "generated_row_count": 0,
            "error": (
                "Planner classified the request "
                "as answerable but did not "
                "generate SQL."
            ),
        }

    reference_sql = (
        references.get(
            case_id
        )
    )

    if not reference_sql:
        raise ValueError(
            "No reference SQL found for "
            f"{case_id}"
        )

    reference_execution = (
        run_query(
            reference_sql
        )
    )

    reference_rows = (
        reference_execution[
            "rows"
        ]
    )

    state = execute_answerable_plan(
        state=state,
        provider_retries=(
            provider_retries
        ),
        retry_delay=(
            retry_delay
        ),
    )

    generated_rows = (
        state.get(
            "query_result",
            [],
        )
    )

    tables_used = (
        state.get(
            "tables_used",
            [],
        )
    )

    last_error = (
        state.get(
            "last_error"
        )
    )

    execution_succeeded = (
        last_error is None
    )

    expected_tables_used = (
        set(
            expected_tables
        ).issubset(
            set(
                tables_used
            )
        )
    )

    result_values_match = False

    if execution_succeeded:
        result_values_match = (
            results_match(
                reference_rows,
                generated_rows,
            )
        )

    correct = (
        execution_succeeded
        and expected_tables_used
        and result_values_match
    )

    return {
        "correct": correct,
        "execution_succeeded": (
            execution_succeeded
        ),
        "expected_tables_used": (
            expected_tables_used
        ),
        "result_values_match": (
            result_values_match
        ),
        "reference_row_count": len(
            reference_rows
        ),
        "generated_row_count": len(
            generated_rows
        ),
        "error": last_error,
    }


def evaluate_non_answerable_case(
    expected_type,
    state,
):
    """
    Score a clarify, unanswerable, or rejected request.

    Correctness requires:
    - correct route
    - a non-empty direct response
    - no SQL generated
    """

    actual_type = state.get(
        "request_type"
    )

    direct_response = (
        state.get(
            "direct_response",
            "",
        )
        or ""
    )

    sql = (
        state.get(
            "sql",
            "",
        )
        or ""
    )

    has_direct_response = bool(
        direct_response.strip()
    )

    sql_generated = bool(
        sql.strip()
    )

    correct = (
        actual_type == expected_type
        and has_direct_response
        and not sql_generated
    )

    return {
        "correct": correct,
        "has_direct_response": (
            has_direct_response
        ),
        "sql_generated": (
            sql_generated
        ),
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the optimized CommercePilot "
            "production planner across the full "
            "60-case regression suite."
        )
    )

    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help=(
            "Skip the first N cases in the "
            "60-case evaluation suite."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Evaluate only the first N remaining "
            "cases."
        ),
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_CASE_DELAY_SECONDS,
        help=(
            "Seconds to wait between cases."
        ),
    )

    parser.add_argument(
        "--provider-retries",
        type=int,
        default=DEFAULT_PROVIDER_RETRIES,
        help=(
            "Number of retries for temporary "
            "provider/network failures."
        ),
    )

    parser.add_argument(
        "--retry-delay",
        type=float,
        default=(
            DEFAULT_PROVIDER_RETRY_DELAY_SECONDS
        ),
        help=(
            "Base delay in seconds between "
            "provider retries."
        ),
    )

    parser.add_argument(
        "--output",
        type=str,
        default=str(
            DEFAULT_RESULTS_FILE
        ),
        help=(
            "JSON file used to store the "
            "evaluation results."
        ),
    )

    args = parser.parse_args()

    cases = load_cases()
    references = load_reference_queries()

    cases = cases[
        args.start:
    ]

    if args.limit is not None:
        cases = cases[
            : args.limit
        ]

    results_file = Path(
        args.output
    )

    if not results_file.is_absolute():
        results_file = (
            PROJECT_ROOT
            / results_file
        )

    print(
        "Inspecting database schema once..."
    )

    schema_context = (
        inspect_schema_once()
    )

    print(
        f"Evaluating {len(cases)} "
        "production-regression cases...\n"
    )

    results = []

    passed = 0
    failed = 0
    infrastructure_errors = 0

    answerable_passed = 0
    answerable_failed = 0

    classification_passed = 0
    classification_failed = 0

    for index, case in enumerate(
        cases,
        start=1,
    ):
        case_id = case["id"]
        question = case["question"]

        expected_type = (
            expected_request_type(
                case
            )
        )

        expected_tables = (
            case.get(
                "expected_tables",
                [],
            )
        )

        print(
            f"[{index}/{len(cases)}] "
            f"{case_id}: "
            f"{question}"
        )

        try:
            state = build_initial_state(
                question=question,
                schema_context=(
                    schema_context
                ),
            )

            plan_update = (
                plan_request(
                    state=state,
                    provider_retries=(
                        args.provider_retries
                    ),
                    retry_delay=(
                        args.retry_delay
                    ),
                )
            )

            state.update(
                plan_update
            )

            actual_type = (
                state.get(
                    "request_type"
                )
            )

            direct_response = (
                state.get(
                    "direct_response",
                    "",
                )
                or ""
            )

            generated_sql = (
                state.get(
                    "sql",
                    "",
                )
                or ""
            )

            classification_correct = (
                actual_type
                == expected_type
            )

            if expected_type == "answerable":

                if not classification_correct:
                    evaluation = {
                        "correct": False,
                        "execution_succeeded": False,
                        "expected_tables_used": False,
                        "result_values_match": False,
                        "reference_row_count": 0,
                        "generated_row_count": 0,
                        "error": (
                            "Planner misclassified "
                            "an answerable request."
                        ),
                    }

                else:
                    evaluation = (
                        evaluate_answerable_case(
                            case=case,
                            state=state,
                            references=references,
                            provider_retries=(
                                args.provider_retries
                            ),
                            retry_delay=(
                                args.retry_delay
                            ),
                        )
                    )

                correct = (
                    classification_correct
                    and evaluation[
                        "correct"
                    ]
                )

                if correct:
                    answerable_passed += 1

                else:
                    answerable_failed += 1

                result_record = {
                    "id": case_id,
                    "category": (
                        case["category"]
                    ),
                    "question": question,
                    "expected_type": (
                        expected_type
                    ),
                    "actual_type": (
                        actual_type
                    ),
                    "classification_correct": (
                        classification_correct
                    ),
                    "correct": correct,
                    "scored": True,
                    "infrastructure_error": False,
                    "direct_response": (
                        direct_response
                    ),
                    "generated_sql": (
                        state.get(
                            "sql",
                            "",
                        )
                    ),
                    "tables_used": (
                        state.get(
                            "tables_used",
                            [],
                        )
                    ),
                    "expected_tables": (
                        expected_tables
                    ),
                    "attempts": (
                        state.get(
                            "attempts",
                            0,
                        )
                    ),
                    "execution_succeeded": (
                        evaluation[
                            "execution_succeeded"
                        ]
                    ),
                    "expected_tables_used": (
                        evaluation[
                            "expected_tables_used"
                        ]
                    ),
                    "result_values_match": (
                        evaluation[
                            "result_values_match"
                        ]
                    ),
                    "reference_row_count": (
                        evaluation[
                            "reference_row_count"
                        ]
                    ),
                    "generated_row_count": (
                        evaluation[
                            "generated_row_count"
                        ]
                    ),
                    "error": (
                        evaluation[
                            "error"
                        ]
                    ),
                }

            else:
                evaluation = (
                    evaluate_non_answerable_case(
                        expected_type=(
                            expected_type
                        ),
                        state=state,
                    )
                )

                correct = (
                    evaluation[
                        "correct"
                    ]
                )

                if correct:
                    classification_passed += 1

                else:
                    classification_failed += 1

                result_record = {
                    "id": case_id,
                    "category": (
                        case["category"]
                    ),
                    "question": question,
                    "expected_type": (
                        expected_type
                    ),
                    "actual_type": (
                        actual_type
                    ),
                    "classification_correct": (
                        classification_correct
                    ),
                    "correct": correct,
                    "scored": True,
                    "infrastructure_error": False,
                    "direct_response": (
                        direct_response
                    ),
                    "generated_sql": (
                        generated_sql
                    ),
                    "sql_generated": (
                        evaluation[
                            "sql_generated"
                        ]
                    ),
                    "has_direct_response": (
                        evaluation[
                            "has_direct_response"
                        ]
                    ),
                    "tables_used": [],
                    "expected_tables": (
                        expected_tables
                    ),
                    "attempts": (
                        state.get(
                            "attempts",
                            0,
                        )
                    ),
                    "execution_succeeded": False,
                    "error": None,
                }

            if correct:
                passed += 1
                print("  PASS")

            else:
                failed += 1
                print("  FAIL")

                print(
                    "  Expected route: "
                    f"{expected_type}"
                )

                print(
                    "  Actual route:   "
                    f"{actual_type}"
                )

                if expected_type == "answerable":
                    if (
                        classification_correct
                        and not result_record[
                            "execution_succeeded"
                        ]
                    ):
                        print(
                            "  SQL execution failed."
                        )

                    elif (
                        classification_correct
                        and not result_record[
                            "expected_tables_used"
                        ]
                    ):
                        print(
                            "  Expected table(s) "
                            "were not used."
                        )

                    elif (
                        classification_correct
                        and not result_record[
                            "result_values_match"
                        ]
                    ):
                        print(
                            "  Generated result "
                            "does not match the "
                            "reference result."
                        )

                    print(
                        "  SQL: "
                        f"{result_record['generated_sql']}"
                    )

                else:
                    print(
                        "  Response: "
                        f"{direct_response}"
                    )

                    print(
                        "  SQL generated: "
                        f"{result_record['sql_generated']}"
                    )

        except Exception as error:
            infrastructure_error = (
                is_provider_error(
                    error
                )
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

                if expected_type == "answerable":
                    answerable_failed += 1

                else:
                    classification_failed += 1

            print(
                f"  Error: {error}"
            )

            result_record = {
                "id": case_id,
                "category": (
                    case["category"]
                ),
                "question": question,
                "expected_type": (
                    expected_type
                ),
                "actual_type": None,
                "classification_correct": False,
                "correct": False,
                "scored": (
                    not infrastructure_error
                ),
                "infrastructure_error": (
                    infrastructure_error
                ),
                "direct_response": "",
                "generated_sql": "",
                "tables_used": [],
                "expected_tables": (
                    expected_tables
                ),
                "attempts": 0,
                "execution_succeeded": False,
                "error": str(
                    error
                ),
            }

        results.append(
            result_record
        )

        print()

        if (
            index < len(cases)
            and args.delay > 0
        ):
            time.sleep(
                args.delay
            )

    scored_cases = (
        passed + failed
    )

    overall_accuracy = (
        passed / scored_cases
        if scored_cases
        else 0.0
    )

    answerable_scored = (
        answerable_passed
        + answerable_failed
    )

    answerable_accuracy = (
        answerable_passed
        / answerable_scored
        if answerable_scored
        else 0.0
    )

    classification_scored = (
        classification_passed
        + classification_failed
    )

    classification_accuracy = (
        classification_passed
        / classification_scored
        if classification_scored
        else 0.0
    )

    output = {
        "summary": {
            "total_cases": len(
                cases
            ),
            "scored_cases": (
                scored_cases
            ),
            "passed": passed,
            "failed": failed,
            "infrastructure_errors": (
                infrastructure_errors
            ),
            "overall_accuracy": (
                overall_accuracy
            ),
            "answerable": {
                "scored_cases": (
                    answerable_scored
                ),
                "passed": (
                    answerable_passed
                ),
                "failed": (
                    answerable_failed
                ),
                "accuracy": (
                    answerable_accuracy
                ),
            },
            "non_answerable": {
                "scored_cases": (
                    classification_scored
                ),
                "passed": (
                    classification_passed
                ),
                "failed": (
                    classification_failed
                ),
                "accuracy": (
                    classification_accuracy
                ),
            },
        },
        "results": results,
    }

    results_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with results_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        "Production regression "
        "evaluation complete."
    )

    print(
        f"Total cases: {len(cases)}"
    )

    print(
        f"Scored cases: {scored_cases}"
    )

    print(
        f"Passed: {passed}"
    )

    print(
        f"Failed: {failed}"
    )

    print(
        "Infrastructure errors: "
        f"{infrastructure_errors}"
    )

    if scored_cases:
        print(
            "Overall accuracy: "
            f"{overall_accuracy:.2%}"
        )

    if answerable_scored:
        print(
            "Answerable accuracy: "
            f"{answerable_accuracy:.2%}"
        )

    if classification_scored:
        print(
            "Non-answerable accuracy: "
            f"{classification_accuracy:.2%}"
        )

    print(
        "Results saved to: "
        f"{results_file}"
    )


if __name__ == "__main__":
    main()