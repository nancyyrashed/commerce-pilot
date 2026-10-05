from sqlglot import exp, parse_one


POSTGRES_DIALECT = "postgres"


def extract_table_names(sql_text: str) -> list[str]:
    """
    Extract the physical PostgreSQL tables referenced by a SQL query.

    Common table expressions (CTEs) are excluded because they are
    temporary query names rather than real database tables.
    """

    statement = parse_one(
        sql_text,
        read=POSTGRES_DIALECT,
    )

    # Collect CTE names so they are not reported as physical tables.
    cte_names = {
        cte.alias_or_name
        for cte in statement.find_all(exp.CTE)
        if cte.alias_or_name
    }

    tables = []
    seen = set()

    for table in statement.find_all(exp.Table):
        table_name = table.name

        if not table_name:
            continue

        if table_name in cte_names:
            continue

        if table_name not in seen:
            seen.add(table_name)
            tables.append(table_name)

    return tables