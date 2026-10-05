import src.agent_graph as agent_graph_module


def _initial_state(
    question: str,
):
    """
    Minimal starting state for graph tests.
    """

    return {
        "question": question,
        "request_type": "",
        "direct_response": "",
        "schema_context": "",
        "sql": "",
        "query_result": [],
        "tables_used": [],
        "attempts": 0,
        "last_error": None,
        "answer": "",
    }


def test_graph_success_first_attempt(
    monkeypatch,
):
    """
    A successful one-row, one-column query should use the
    deterministic simple-result answer path.
    """

    def fake_inspect_schema(state):
        return {
            "schema_context": (
                "orders: order_id (text)"
            ),
        }

    def fake_plan(state):
        return {
            "request_type": "answerable",
            "direct_response": "",
            "sql": (
                "SELECT COUNT(*) AS total_orders "
                "FROM orders"
            ),
            "attempts": 1,
            "last_error": None,
        }

    def fake_execute_sql(state):
        return {
            "query_result": [
                {
                    "total_orders": 99441,
                }
            ],
            "tables_used": [
                "orders",
            ],
            "last_error": None,
        }

    def fake_simple_answer(state):
        return {
            "answer": (
                "Total orders: 99,441."
            ),
        }

    def forbidden_final_answer(state):
        raise AssertionError(
            "final_answer_node should not run "
            "for a one-cell result."
        )

    monkeypatch.setattr(
        agent_graph_module,
        "inspect_schema_node",
        fake_inspect_schema,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "classify_and_generate_sql_node",
        fake_plan,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "execute_sql_node",
        fake_execute_sql,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "simple_result_answer_node",
        fake_simple_answer,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "final_answer_node",
        forbidden_final_answer,
    )

    graph = (
        agent_graph_module.build_agent_graph()
    )

    result = graph.invoke(
        _initial_state(
            "How many orders are there?"
        )
    )

    assert (
        result["request_type"]
        == "answerable"
    )

    assert result["attempts"] == 1

    assert (
        result["answer"]
        == "Total orders: 99,441."
    )

    assert result["tables_used"] == [
        "orders",
    ]

    assert result["last_error"] is None


def test_graph_repairs_failed_sql(
    monkeypatch,
):
    """
    A failed initial SQL execution should route to SQL repair.

    This test returns a multi-column result after repair so the
    complex-result path to final_answer_node is also verified.
    """

    def fake_inspect_schema(state):
        return {
            "schema_context": (
                "orders: order_id (text), "
                "customer_id (text)"
            ),
        }

    def fake_plan(state):
        return {
            "request_type": "answerable",
            "direct_response": "",
            "sql": (
                "SELECT bad_column "
                "FROM orders"
            ),
            "attempts": 1,
            "last_error": None,
        }

    def fake_generate_sql(state):
        return {
            "sql": (
                "SELECT "
                "COUNT(*) AS total_orders, "
                "COUNT(DISTINCT customer_id) "
                "AS customer_records "
                "FROM orders"
            ),
            "attempts": (
                state.get(
                    "attempts",
                    0,
                )
                + 1
            ),
            "last_error": None,
        }

    def fake_execute_sql(state):
        if state["attempts"] == 1:
            return {
                "query_result": [],
                "tables_used": [],
                "last_error": (
                    'column "bad_column" '
                    "does not exist"
                ),
            }

        return {
            "query_result": [
                {
                    "total_orders": 99441,
                    "customer_records": 99441,
                }
            ],
            "tables_used": [
                "orders",
            ],
            "last_error": None,
        }

    def forbidden_simple_answer(state):
        raise AssertionError(
            "simple_result_answer_node should not run "
            "for a multi-column result."
        )

    def fake_final_answer(state):
        return {
            "answer": (
                "The dataset contains 99,441 orders "
                "and 99,441 customer records."
            ),
        }

    monkeypatch.setattr(
        agent_graph_module,
        "inspect_schema_node",
        fake_inspect_schema,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "classify_and_generate_sql_node",
        fake_plan,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "generate_sql_node",
        fake_generate_sql,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "execute_sql_node",
        fake_execute_sql,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "simple_result_answer_node",
        forbidden_simple_answer,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "final_answer_node",
        fake_final_answer,
    )

    graph = (
        agent_graph_module.build_agent_graph()
    )

    result = graph.invoke(
        _initial_state(
            "How many orders and customer "
            "records are there?"
        )
    )

    assert result["attempts"] == 2

    assert result["last_error"] is None

    assert (
        result["answer"]
        == (
            "The dataset contains 99,441 orders "
            "and 99,441 customer records."
        )
    )


def test_graph_stops_after_max_attempts(
    monkeypatch,
):
    """
    The graph should stop retrying after MAX_ATTEMPTS failed
    SQL-generation attempts.
    """

    def fake_inspect_schema(state):
        return {
            "schema_context": (
                "orders: order_id (text)"
            ),
        }

    def fake_plan(state):
        return {
            "request_type": "answerable",
            "direct_response": "",
            "sql": (
                "SELECT bad_column "
                "FROM orders"
            ),
            "attempts": 1,
            "last_error": None,
        }

    def fake_generate_sql(state):
        return {
            "sql": (
                "SELECT bad_column "
                "FROM orders"
            ),
            "attempts": (
                state.get(
                    "attempts",
                    0,
                )
                + 1
            ),
            "last_error": None,
        }

    def fake_execute_sql(state):
        return {
            "query_result": [],
            "tables_used": [],
            "last_error": (
                'column "bad_column" '
                "does not exist"
            ),
        }

    def forbidden_answer_node(state):
        raise AssertionError(
            "No answer-generation node should run "
            "after repeated SQL failure."
        )

    monkeypatch.setattr(
        agent_graph_module,
        "inspect_schema_node",
        fake_inspect_schema,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "classify_and_generate_sql_node",
        fake_plan,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "generate_sql_node",
        fake_generate_sql,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "execute_sql_node",
        fake_execute_sql,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "simple_result_answer_node",
        forbidden_answer_node,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "final_answer_node",
        forbidden_answer_node,
    )

    graph = (
        agent_graph_module.build_agent_graph()
    )

    result = graph.invoke(
        _initial_state(
            "How many orders are there?"
        )
    )

    assert (
        result["attempts"]
        == agent_graph_module.MAX_ATTEMPTS
    )

    assert result["last_error"] is not None

    assert result["answer"] == ""


def test_clarify_request_stops_before_sql(
    monkeypatch,
):
    """
    Ambiguous requests should stop after the combined planner
    without executing SQL.
    """

    def fake_inspect_schema(state):
        return {
            "schema_context": (
                "orders: order_id (text)"
            ),
        }

    def fake_plan(state):
        return {
            "request_type": "clarify",
            "direct_response": (
                "Which metric would you like "
                "to use?"
            ),
            "sql": "",
            "attempts": 0,
            "last_error": None,
        }

    def forbidden_node(state):
        raise AssertionError(
            "SQL or answer workflow should not run "
            "for clarify requests."
        )

    monkeypatch.setattr(
        agent_graph_module,
        "inspect_schema_node",
        fake_inspect_schema,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "classify_and_generate_sql_node",
        fake_plan,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "execute_sql_node",
        forbidden_node,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "generate_sql_node",
        forbidden_node,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "simple_result_answer_node",
        forbidden_node,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "final_answer_node",
        forbidden_node,
    )

    graph = (
        agent_graph_module.build_agent_graph()
    )

    result = graph.invoke(
        _initial_state(
            "Which category performed best?"
        )
    )

    assert (
        result["request_type"]
        == "clarify"
    )

    assert result["attempts"] == 0

    assert (
        result["direct_response"]
        == "Which metric would you like to use?"
    )


def test_unanswerable_request_stops_before_sql(
    monkeypatch,
):
    """
    Requests requiring unavailable data should stop without
    executing SQL.
    """

    def fake_inspect_schema(state):
        return {
            "schema_context": (
                "orders: order_id (text)"
            ),
        }

    def fake_plan(state):
        return {
            "request_type": "unanswerable",
            "direct_response": (
                "Profit data is unavailable."
            ),
            "sql": "",
            "attempts": 0,
            "last_error": None,
        }

    def forbidden_node(state):
        raise AssertionError(
            "SQL or answer workflow should not run "
            "for unanswerable requests."
        )

    monkeypatch.setattr(
        agent_graph_module,
        "inspect_schema_node",
        fake_inspect_schema,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "classify_and_generate_sql_node",
        fake_plan,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "execute_sql_node",
        forbidden_node,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "generate_sql_node",
        forbidden_node,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "simple_result_answer_node",
        forbidden_node,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "final_answer_node",
        forbidden_node,
    )

    graph = (
        agent_graph_module.build_agent_graph()
    )

    result = graph.invoke(
        _initial_state(
            "What was our profit?"
        )
    )

    assert (
        result["request_type"]
        == "unanswerable"
    )

    assert result["attempts"] == 0

    assert (
        result["direct_response"]
        == "Profit data is unavailable."
    )


def test_rejected_request_stops_before_sql(
    monkeypatch,
):
    """
    Unsafe requests should be rejected by the combined planner
    before SQL execution occurs.
    """

    def fake_inspect_schema(state):
        return {
            "schema_context": (
                "orders: order_id (text)"
            ),
        }

    def fake_plan(state):
        return {
            "request_type": "reject",
            "direct_response": (
                "CommercePilot only performs "
                "read-only analytics."
            ),
            "sql": "",
            "attempts": 0,
            "last_error": None,
        }

    def forbidden_node(state):
        raise AssertionError(
            "SQL or answer workflow should not run "
            "for rejected requests."
        )

    monkeypatch.setattr(
        agent_graph_module,
        "inspect_schema_node",
        fake_inspect_schema,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "classify_and_generate_sql_node",
        fake_plan,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "execute_sql_node",
        forbidden_node,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "generate_sql_node",
        forbidden_node,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "simple_result_answer_node",
        forbidden_node,
    )

    monkeypatch.setattr(
        agent_graph_module,
        "final_answer_node",
        forbidden_node,
    )

    graph = (
        agent_graph_module.build_agent_graph()
    )

    result = graph.invoke(
        _initial_state(
            "Drop the orders table."
        )
    )

    assert (
        result["request_type"]
        == "reject"
    )

    assert result["attempts"] == 0

    assert (
        result["direct_response"]
        == (
            "CommercePilot only performs "
            "read-only analytics."
        )
    )