from decimal import Decimal
from datetime import date, datetime

from evaluation.evaluate_answerable import results_match

from datetime import date, datetime

def test_results_match_treats_midnight_datetime_as_same_date():
    reference_rows = [
        {
            "month": datetime(2018, 1, 1, 0, 0),
            "sales_value": 924645.00,
        }
    ]

    generated_rows = [
        {
            "month": date(2018, 1, 1),
            "sales_value": 924645.00,
        }
    ]

    assert results_match(reference_rows, generated_rows)


def test_results_match_ignores_cosmetic_text_differences():
    """
    Equivalent categorical labels should match even when capitalization
    or separators differ.
    """

    reference_rows = [
        {
            "delivery_group": "late",
            "average_review_score": Decimal(
                "2.5664935064935065"
            ),
        },
        {
            "delivery_group": "on_time",
            "average_review_score": Decimal(
                "4.2937182046856846"
            ),
        },
    ]

    generated_rows = [
        {
            "delivery_status": "Late",
            "avg_review_score": Decimal(
                "2.5664935064935065"
            ),
        },
        {
            "delivery_status": "On-time",
            "avg_review_score": Decimal(
                "4.2937182046856846"
            ),
        },
    ]

    assert results_match(
        reference_rows,
        generated_rows,
    )


def test_results_match_allows_extra_generated_columns():
    """
    Extra useful columns should not make an otherwise correct result
    fail evaluation.
    """

    reference_rows = [
        {
            "seller_id": "seller_a",
            "sales_share_pct": Decimal(
                "1.7168094576840657"
            ),
        },
        {
            "seller_id": "seller_b",
            "sales_share_pct": Decimal(
                "1.6483793151637035"
            ),
        },
    ]

    generated_rows = [
        {
            "seller_id": "seller_a",
            "sales": Decimal("226987.93"),
            "percentage_of_total": Decimal(
                "1.72"
            ),
        },
        {
            "seller_id": "seller_b",
            "sales": Decimal("217940.44"),
            "percentage_of_total": Decimal(
                "1.65"
            ),
        },
    ]

    assert results_match(
        reference_rows,
        generated_rows,
    )


def test_results_match_rejects_wrong_values():
    """
    Semantic differences must still fail.
    """

    reference_rows = [
        {
            "customer_unique_id": "customer_a",
            "sales_value": Decimal("3109.99"),
        }
    ]

    generated_rows = [
        {
            "customer_unique_id": "customer_b",
            "sales_value": Decimal("2238.42"),
        }
    ]

    assert not results_match(
        reference_rows,
        generated_rows,
    )


def test_results_match_rejects_wrong_row_count():
    """
    A query returning the wrong number of rows must still fail even if
    some returned values are correct.
    """

    reference_rows = [
        {
            "percentage": Decimal("25.00"),
        }
    ]

    generated_rows = [
        {
            "category": "A",
            "percentage": Decimal("10.00"),
        },
        {
            "category": "B",
            "percentage": Decimal("15.00"),
        },
    ]

    assert not results_match(
        reference_rows,
        generated_rows,
    )