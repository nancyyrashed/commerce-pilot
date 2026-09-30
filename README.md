# CommercePilot

A natural-language-to-SQL analytics agent for exploring the
Brazilian E-Commerce Public Dataset by Olist.

## Project goal

Answer business questions by inspecting a database, generating SQL,
validating and executing queries, and correcting errors within a
limited number of attempts.

Planned answers will include the explanation, SQL, tables used,
attempt count, and execution time.

## Current progress

Phase 0: Local setup.

Implemented:
- PostgreSQL 17 running through Docker Compose.
- Python-to-PostgreSQL connection test.
- Environment-based database configuration.
- Plain-Python simulation of an agent retry loop.

The agent-loop sketch uses simulated responses.
The Olist dataset and real LLM integration are not implemented yet.

## Planned architecture

- Local: Streamlit → FastAPI → LangGraph agent → PostgreSQL.
- Public demo: Streamlit → shared agent core → read-only SQLite sample.

Dataset redistribution permissions and hosting terms will be verified
before publishing the demo.

## Local setup

Requirements: Python 3.11 and Docker Desktop.

Run these commands from the project folder on Windows:

```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

For a fresh clone, copy `.env.example` to `.env` and replace the
password placeholder with your own local database password.
Keep `.env` private.

With Docker Desktop running:

```cmd
docker compose up -d
python scripts/check_db.py
```

Run the simulated agent loop:

```cmd
python scripts/agent_loop_sketch.py
```

## Data and credentials

Raw dataset files and private credentials are excluded from Git.
Dataset attribution and verified license details will be added
during the data phase.