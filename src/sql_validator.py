from sqlglot import exp, parse
from sqlglot.errors import ParseError


POSTGRES_DIALECT = "postgres"

# No query result returned to the agent/browser may exceed this size.
MAX_ROWS = 100


class SQLValidationError(ValueError):
    """Raised when generated SQL violates CommercePilot's safety rules."""


def _parse_single_statement(sql_text):
    """Parse SQL and require exactly one PostgreSQL statement."""

    if not isinstance(sql_text, str):
        raise TypeError("SQL must be provided as a string.")

    if not sql_text.strip():
        raise SQLValidationError("SQL query cannot be empty.")

    try:
        statements = parse(
            sql_text,
            read=POSTGRES_DIALECT,
        )
    except ParseError as error:
        raise SQLValidationError(
            "SQL could not be parsed as valid PostgreSQL."
        ) from error

    # Remove any empty parsed statements, if present.
    statements = [
        statement
        for statement in statements
        if statement is not None
    ]

    if len(statements) != 1:
        raise SQLValidationError(
            "Exactly one SQL statement is allowed."
        )

    return statements[0]


def _ensure_read_only(statement):
    """
    Require a query expression and reject any operation that could
    modify data, create objects, or acquire row locks.
    """

    if not isinstance(statement, exp.Query):
        raise SQLValidationError(
            "Only read-only SELECT queries are allowed."
        )

    # PostgreSQL SELECT ... INTO creates a table.
    if statement.find(exp.Into):
        raise SQLValidationError(
            "SELECT INTO is not allowed."
        )

    # Reject write operations even when hidden inside a CTE.
    if statement.find(exp.DML):
        raise SQLValidationError(
            "Data-modifying operations are not allowed."
        )

    # Reject SELECT ... FOR UPDATE / FOR SHARE locking reads.
    if statement.find(exp.Lock):
        raise SQLValidationError(
            "Locking queries are not allowed."
        )


def _get_literal_limit(statement):
    """
    Return an integer LIMIT when one is explicitly present.

    If there is no LIMIT, return None.
    """

    limit_expression = statement.args.get("limit")

    if limit_expression is None:
        return None

    value = limit_expression.expression

    # Only treat a plain numeric literal as a trusted existing cap.
    if not isinstance(value, exp.Literal):
        return None

    if not value.is_int:
        return None

    return int(value.this)


def _enforce_row_limit(statement, max_rows):
    """Return a query whose result cannot exceed max_rows."""

    existing_limit = _get_literal_limit(statement)

    # Preserve a stricter user/model limit.
    if (
        existing_limit is not None
        and 0 <= existing_limit <= max_rows
    ):
        return statement

    # No usable limit, or a limit larger than our safety cap:
    # replace it with CommercePilot's maximum.
    return statement.limit(max_rows)


def validate_sql(sql_text, max_rows=MAX_ROWS):
    """
    Validate model-generated SQL and return safe PostgreSQL SQL.

    Rules:
    - exactly one statement
    - query/SELECT expressions only
    - no SELECT INTO
    - hard maximum result-row limit
    """

    if not isinstance(max_rows, int) or isinstance(max_rows, bool):
        raise TypeError("max_rows must be an integer.")

    if max_rows < 1:
        raise ValueError("max_rows must be at least 1.")

    statement = _parse_single_statement(sql_text)

    _ensure_read_only(statement)

    safe_statement = _enforce_row_limit(
        statement,
        max_rows,
    )

    return safe_statement.sql(
        dialect=POSTGRES_DIALECT,
    )