# Simulated tools and model decisions for learning the agent loop.
# No real database connection or LLM call happens in this script.

MAX_ATTEMPTS = 3


def list_tables():
    # Pretend the agent inspected a database containing these tables.
    return ["orders", "customers"]


def choose_sql(state):
    # Simulate a model making a mistake on its first attempt.
    if state["last_error"] is None:
        return "SELECT COUNT(*) FROM orderz;"

    # Simulate the model correcting its query after reading the error.
    return "SELECT COUNT(*) FROM orders;"


def run_query(sql):
    # Simulate the database response to the misspelled table name.
    if sql == "SELECT COUNT(*) FROM orderz;":
        raise ValueError("Table 'orderz' does not exist.")

    # Return an invented result for the expected corrected query.
    if sql == "SELECT COUNT(*) FROM orders;":
        return {"order_count": 42}

    raise ValueError("This simulated tool does not support that query.")


def main():
    # State holds the information carried between steps.
    state = {
        "question": "How many orders are there?",
        "tables": list_tables(),
        "attempts": 0,
        "last_error": None,
        "result": None,
    }

    print(f"Question: {state['question']}")
    print(f"Available tables: {state['tables']}")

    # Limit attempts so repeated failures cannot create an endless loop.
    while state["attempts"] < MAX_ATTEMPTS:
        state["attempts"] += 1
        sql = choose_sql(state)
        print(f"\nAttempt {state['attempts']}: {sql}")

        try:
            state["result"] = run_query(sql)
        except ValueError as error:
            # Save the error so the next decision can use it.
            state["last_error"] = str(error)
            print(f"Error: {state['last_error']}")
            continue

        # A successful query ends the loop.
        state["last_error"] = None
        print(f"Success: {state['result']}")
        break
    else:
        # This runs only if all attempts finish without a break.
        print("Stopped: maximum attempts reached.")


if __name__ == "__main__":
    main()