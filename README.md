# CommercePilot

A natural-language-to-SQL analytics agent for exploring the  
Brazilian E-Commerce Public Dataset by Olist.

## Project goal

Answer business questions in plain English by inspecting a PostgreSQL database, classifying the request, generating SQL when appropriate, validating and executing queries safely, repairing failed queries within a bounded number of attempts, and returning a grounded natural-language answer.

CommercePilot currently returns:

- a natural-language answer
- the executed SQL
- tables used
- SQL-generation attempt count
- row count
- success/failure status
- final error information when applicable
- end-to-end request duration from the FastAPI layer

## Current progress

Phase 0: Local setup. ✅  
Phase 1: Data layer. ✅  
Phase 2: Database tools and SQL guardrails. ✅  
Phase 3: LangGraph agent. ✅  
Phase 4: Evaluation. ✅  
Phase 5: Backend and frontend. ✅

Implemented:

- PostgreSQL 17 running through Docker Compose.
- Python-to-PostgreSQL connection test.
- Environment-based database configuration.
- Plain-Python simulation of an agent retry loop.
- Full Olist dataset loaded into PostgreSQL.
- All 9 source datasets loaded with validated row counts.
- Primary and foreign key relationships defined.
- Data types and cleaning rules implemented.
- Exact duplicate geolocation rows removed.
- Data dictionary and dataset setup documentation created.
- Dedicated `commercepilot_reader` role created and verified as read-only.
- `commercepilot_reader` configured with a 10-second PostgreSQL statement timeout.
- Full local PostgreSQL database size verified at approximately 195 MB.
- Database inspection tools implemented:
  - `list_tables()`
  - `describe_table()`
  - `sample_rows()`
- Safe SQL execution through `run_query()`.
- PostgreSQL SQL parsing and validation with `sqlglot`.
- Single-statement enforcement.
- Read-only query enforcement.
- `SELECT INTO` protection.
- Data-modifying CTE protection.
- Locking-query protection such as `FOR UPDATE`.
- Hard maximum result limit of 100 rows.
- Groq LLM integration through LangChain.
- LangGraph agent state and workflow.
- Structured request routing into answerable, clarification-needed, unanswerable and rejected requests.
- Cached live PostgreSQL schema context.
- Combined request classification and first SQL generation in one structured LLM call.
- Prompt-based CommercePilot business rules for SQL generation.
- Natural-language-to-PostgreSQL SQL generation.
- Automatic SQL execution through the Phase 2 safety layer.
- Bounded SQL repair loop with a maximum of 3 generation attempts.
- Database and validation errors captured and fed back into SQL repair.
- Deterministic fast path for successful one-row, one-column results.
- Percentage-aware scalar formatting for percentage/percent/pct result aliases.
- Grounded LLM answer generation for more complex result sets.
- Currency symbols prevented unless explicitly supported by the question or result.
- Deterministic `tables_used` extraction from executed SQL using `sqlglot`.
- Pydantic `AgentResponse` structured output.
- `run_agent()` service layer for a clean application interface.
- FastAPI application layer.
- `GET /health`.
- `POST /api/ask`.
- Pydantic API request and response schemas.
- 500-character API question limit.
- Safe provider-rate-limit handling with HTTP 429.
- Safe generic HTTP 500 handling without leaking internal details.
- Local-development CORS configuration.
- End-to-end API request timing.
- React + Vite frontend.
- Natural-language query workspace with example questions.
- Loading and error states.
- Answer, SQL and execution-detail tabs.
- SQL copy control.
- Markdown rendering for rich answer formatting such as bullet lists and bold text.
- Tables, attempts, rows returned and request-duration metrics.
- FastAPI serving the compiled React production build.
- Mocked LangGraph routing tests covering success, repair, retry exhaustion, scalar-result routing, complex-result routing and non-answerable routing.
- FastAPI API tests.
- 60-question evaluation suite covering SQL execution, ambiguity, unavailable data and adversarial requests.
- Reference SQL for all 45 answerable evaluation questions.
- Semantic result comparison that tolerates harmless SQL/output differences while detecting incorrect results.
- Infrastructure errors separated from scored model failures.
- Production-path regression evaluator covering the optimized agent architecture.
- Final production regression result:
  - 45/45 answerable cases passed.
  - 15/15 non-answerable routing/safety cases passed.
  - 60/60 total cases passed.
  - 0 failures.
  - 0 infrastructure errors in the final production regression artifact.
- **41 automated Python tests passing.**
- Frontend lint passing.
- Frontend production build passing.
- Integrated FastAPI → React static serving verified.
- Agent-stage timing moved from direct console prints to debug logging.
- Direct Groq SDK dependency pinned explicitly for the API layer.

The original plain-Python retry-loop sketch remains in the repository as an early development artifact. The production agent now uses LangGraph and Groq.

## Architecture

### Local

```text
React + Vite
     ↓
FastAPI
     ↓
LangGraph agent
     ↓
cached PostgreSQL schema context
     ↓
combined classification + initial SQL generation
     ↓
sqlglot validation
     ↓
commercepilot_reader
     ↓
PostgreSQL in Docker
```

### Public demo

The deployment target is:

```text
Browser
   ↓
Render
   ├── FastAPI API
   └── compiled React frontend
          ↓
       LangGraph agent
          ↓
       Neon PostgreSQL
```

The React frontend is built into static files and served by FastAPI, keeping the deployed application to one Render web service.

PostgreSQL is used everywhere. There is no separate SQLite demo database.

## Local setup

Requirements:

- Python 3.11
- Node.js 18+
- Docker Desktop

Run these commands from the project folder on Windows:

```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
npm --prefix frontend install
```

For a fresh clone, copy `.env.example` to `.env` and provide the required local values.

The local environment includes PostgreSQL credentials and Groq configuration such as:

```text
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-20b
```

Keep `.env` private.

With Docker Desktop running:

```cmd
docker compose up -d
python scripts/check_db.py
```

The original simulated agent loop can still be run with:

```cmd
python scripts/agent_loop_sketch.py
```

The real CommercePilot agent is available directly through:

```python
from src.agent_service import run_agent

result = run_agent(
    "How many orders are in the dataset?"
)
```

### Run the FastAPI backend

```cmd
python -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

API endpoints:

```text
GET  /health
POST /api/ask
```

### Run the React development server

In another terminal:

```cmd
npm --prefix frontend run dev
```

### Build and serve the integrated production frontend locally

Build React:

```cmd
npm --prefix frontend run build
```

Then run FastAPI:

```cmd
python -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/
```

FastAPI serves the generated `frontend/dist` assets directly.

## Dataset setup

Raw Olist CSV files are excluded from Git.

Place the dataset files in:

```text
data/raw/
```

Then load the full PostgreSQL database:

```cmd
python scripts/load_data.py
```

Create and verify the read-only database role:

```cmd
python scripts/setup_readonly.py
```

Detailed setup instructions are available in:

- [Dataset Setup](docs/data_setup.md)
- [Data Dictionary](docs/data_dictionary.md)

## Data and credentials

Raw dataset files and private credentials are excluded from Git.

The project uses the **Brazilian E-Commerce Public Dataset by Olist**, reported on Kaggle under **CC BY-NC-SA 4.0**.

Dataset attribution and license information are documented in the data dictionary and will remain visible in the public repository and demo.

Private values such as:

- PostgreSQL passwords
- Groq API keys
- Neon database URLs

must remain in environment variables and must never be committed to Git.

## SQL safety

Model-generated SQL is never sent directly to PostgreSQL without deterministic validation.

For answerable requests, the current execution path is:

```text
User question
     ↓
cached/live schema inspection
     ↓
combined request classification
+ initial SQL generation
     ↓
answerable?
     ├── no  → direct response → END
     │
     └── yes
          ↓
sqlglot parsing
          ↓
single-statement validation
          ↓
read-only validation
          ↓
hard LIMIT 100
          ↓
run_query()
          ↓
commercepilot_reader
          ↓
10-second PostgreSQL statement timeout
          ↓
PostgreSQL
```

If execution fails:

```text
validation/database error
     ↓
stored in agent state
     ↓
previous SQL + error returned to Groq
     ↓
SQL repair
     ↓
validation and execution again
```

The repair loop is bounded to a maximum of **3 SQL-generation attempts**.

The validator currently blocks:

- `INSERT`
- `UPDATE`
- `DELETE`
- `DROP`
- other non-query statements
- multiple SQL statements
- `SELECT INTO`
- data-changing operations hidden inside CTEs
- locking queries such as `FOR UPDATE`

Database permissions provide an additional independent safety layer even if application validation fails.

## Agent workflow

The optimized LangGraph workflow is:

```text
START
  ↓
inspect_schema
  ↓
classify_and_generate_sql
  ↓
request type?
  ├── clarify / unanswerable / reject → END
  │
  └── answerable
       ↓
execute_sql
       ↓
success?
  ├── no
  │    ↓
  │ attempts < 3?
  │    ├── yes → generate_sql (repair)
  │    │          ↓
  │    │       execute_sql
  │    └── no  → END
  │
  └── yes
       ↓
result shape?
  ├── one row + one column
  │      ↓
  │ simple_result_answer
  │      ↓
  │     END
  │
  └── complex result
         ↓
     final_answer
         ↓
        END
```

The standalone classification node is retained for component evaluation and tests, while the production graph uses the combined planner.

Non-answerable requests are handled without SQL execution:

- `clarify` — ask one concise question to resolve ambiguity.
- `unanswerable` — explain which required data is unavailable.
- `reject` — refuse unsafe database actions or requests for secrets.

### Latency-oriented agent changes

Phase 5 reduced unnecessary work in the normal request path:

- schema inspection is cached after the first request
- classification and first SQL generation are combined into one structured Groq call
- one-row, one-column results use deterministic answer formatting instead of a second LLM call
- SQL repair remains available only when execution fails
- complex result sets still use the grounded final-answer LLM node

The main remaining latency source is the external Groq model call rather than PostgreSQL query execution for typical analytical requests.

## Main components

- `src/agent_state.py` — shared LangGraph state.
- `src/classification_models.py` — structured request-classification and combined planning schemas.
- `src/agent_nodes.py` — schema inspection, planning, SQL generation/repair, SQL execution and answer nodes.
- `src/agent_graph.py` — optimized LangGraph workflow and retry routing.
- `src/llm.py` — Groq chat-model configuration.
- `src/prompts.py` — request-classification, request-plan, SQL-generation and final-answer prompts.
- `src/sql_validator.py` — deterministic SQL safety validation.
- `src/sql_metadata.py` — deterministic table extraction.
- `src/database_tools.py` — PostgreSQL inspection and safe query execution.
- `src/response_models.py` — agent response schema.
- `src/agent_service.py` — application-facing `run_agent()` interface.
- `src/api_models.py` — FastAPI request/response schemas.
- `src/api.py` — FastAPI routes, safe exception handling and compiled-frontend serving.
- `frontend/` — React + Vite user interface.
- `evaluation/` — benchmark definitions, reference SQL, evaluators and final result artifacts.

## Structured API response

`POST /api/ask` returns a validated response shaped like:

```json
{
  "answer": "Total orders: 99,441.",
  "sql": "SELECT COUNT(*) AS total_orders FROM orders LIMIT 100",
  "tables_used": [
    "orders"
  ],
  "attempts": 1,
  "row_count": 1,
  "success": true,
  "error": null,
  "duration_ms": 3630.0
}
```

The exact duration varies by request and external LLM latency.

## Testing

Automated pytest coverage currently includes:

### SQL validation and database tools

- default row-limit insertion
- preservation of smaller limits
- reduction of oversized limits
- destructive SQL rejection
- multi-statement rejection
- `SELECT INTO` rejection
- hidden data-changing CTE rejection
- locking-query rejection
- valid CTE queries
- table discovery
- schema inspection
- table sampling
- safe query execution
- hard result limits

### LangGraph workflow

- successful execution on the first attempt
- scalar-result fast-path routing
- complex-result final-answer routing
- failed SQL routed back to generation for repair
- successful completion after SQL repair
- maximum retry enforcement
- clarification routing
- unanswerable routing
- rejected-request routing

The LangGraph routing tests use mocked nodes, so they do not consume Groq quota.

### FastAPI

API tests cover:

- `/health`
- request validation
- structured `/api/ask` responses
- provider rate-limit handling
- safe internal-error handling
- CORS behavior

### Evaluation matching

The evaluation comparator has regression tests covering:

- cosmetic text differences
- extra generated columns
- detection of incorrect values
- detection of incorrect row counts
- equivalence between dates and midnight timestamps

Run the full Python test suite with:

```cmd
python -m pytest
```

Current result:

```text
41 tests passed
```

Frontend checks:

```cmd
npm --prefix frontend run lint
npm --prefix frontend run build
```

Both currently pass.

The production React build has also been verified when served through FastAPI.

## Evaluation

Phase 4 introduced a hand-checked 60-question evaluation suite:

```text
20 simple questions
15 joins and aggregations
10 multi-step questions
5 ambiguous questions
5 unanswerable questions
5 adversarial questions
-------------------------
60 total questions
```

The 45 answerable questions have hand-written reference SQL.

Generated SQL is evaluated primarily by **execution behavior and result equivalence**, not exact SQL-string matching. This allows semantically equivalent SQL to pass even when aliases, column ordering or harmless formatting differ.

The semantic comparator:

- normalizes cosmetic text differences
- compares numeric values at practical precision
- allows harmless extra generated columns
- ignores alias differences when the result values are equivalent
- compares rows independent of row order where appropriate
- treats a date and the same midnight timestamp as equivalent
- still rejects incorrect values and incorrect row counts

Classification evaluation verifies the expected behavior for:

- ambiguous questions → clarification
- unavailable-data questions → unanswerable
- unsafe/adversarial requests → reject

### Evaluation refinement history

The first full answerable evaluation did not achieve a perfect score.

Initial strict run:

```text
38/45 answerable cases passed
84.44% execution accuracy
```

Reviewing the failures showed that some were evaluation false negatives rather than incorrect SQL. The semantic result comparator was improved to handle legitimate differences such as aliases, harmless extra columns, numeric precision, row ordering, and equivalent date/midnight-timestamp values.

Re-scoring the same generated SQL after those evaluator fixes produced:

```text
41/45 answerable cases passed
91.11% execution accuracy
```

The remaining failures were genuine SQL-semantic errors rather than evaluation issues. They involved general issues such as:

- correct use of `customer_unique_id` for real customer identity
- consistent numerator/denominator grain for repeat-customer percentages
- separating repeat-customer identification from the delivered-order filter used for sales value
- preserving payment-record grain when averaging payment installments

These failures were used to strengthen **general SQL-generation rules** in the system prompt rather than adding question-specific answers.

### Final Phase 4 regression benchmark

```text
Answerable SQL evaluation: 45/45 passed
Classification evaluation: 15/15 passed
----------------------------------------
Full evaluation suite:      60/60 passed

Answerable execution accuracy: 100.00%
Classification accuracy:       100.00%
Infrastructure errors:         0
```

Official Phase 4 result artifacts:

- `evaluation/answerable_final_results.json`
- `evaluation/classification_results.json`

### Phase 5 production regression

Phase 5 added a production-path evaluator that exercises the optimized architecture rather than the older separated component path.

It validates:

- combined request planning
- initial SQL generation
- safe execution
- repair behavior
- expected table usage
- semantic result equivalence
- clarification routing
- unavailable-data routing
- adversarial rejection

Production regression also exposed two additional general semantic requirements that were strengthened in the SQL prompt:

- time-series comparisons should preserve the first chronological period when the previous-period comparison is naturally `NULL`, and should retain native date/timestamp grouping values unless text formatting is explicitly requested
- user-facing product-category names should use the English translation when available even when category calculations pass through CTEs or subqueries

Final production regression result:

```text
Answerable cases:       45/45 passed
Non-answerable cases:   15/15 passed
------------------------------------
Full production suite:  60/60 passed

Failures:               0
Infrastructure errors:  0
Overall accuracy:       100.00%
```

Official production regression artifact:

- `evaluation/production_regression_final.json`

Evaluation definitions and references:

- `evaluation/eval_questions.json`
- `evaluation/reference_queries.json`

Evaluation runners:

- `evaluation/evaluate_answerable.py`
- `evaluation/evaluate_classification.py`
- `evaluation/evaluate_production_agent.py`

The 60/60 results are **post-refinement regression benchmarks**, not untouched held-out test sets. Earlier benchmark failures informed evaluator improvements and general prompt refinements. The results demonstrate that the refined agent passes the project's complete regression suite; they should not be interpreted as 100% accuracy on arbitrary unseen natural-language questions.

## Frontend

The React interface includes:

- CommercePilot branding
- Olist dataset summary
- natural-language query box
- 500-character counter
- suggested example questions
- read-only safety indicator
- loading state
- safe error display
- answer tab
- executed-SQL tab
- execution-details tab
- SQL copy button
- tables-used display
- attempt count
- returned-row count
- request-duration display

The interface intentionally describes the database as PostgreSQL/read-only and the dataset as loaded without pretending those static labels are live health checks.

## Project roadmap

### Phase 0 — Setup ✅

Completed:

- local development foundation
- virtual environment
- environment-variable configuration
- Docker Compose
- PostgreSQL connectivity
- initial plain-Python retry-loop sketch

### Phase 1 — Data ✅

Completed:

- full Olist dataset loading
- PostgreSQL schema
- table relationships
- data cleaning
- row-count validation
- read-only database role
- statement timeout
- data dictionary
- reproducible dataset setup documentation

### Phase 2 — Tools and guardrails ✅

Completed:

- database inspection tools
- safe SQL execution
- `sqlglot` validation
- SELECT-only protection
- one-statement enforcement
- result-row limits
- protection against hidden data modifications
- locking-query protection
- read-only PostgreSQL execution
- automated security and integration tests

### Phase 3 — Agent ✅

Completed:

- Groq LLM integration
- LangChain Groq wrapper
- LangGraph agent state
- request classification
- clarification/unanswerable/reject routing
- live schema inspection
- SQL-generation node
- CommercePilot business rules in the SQL prompt
- safe query-execution node
- database-error capture
- bounded SQL repair
- maximum retry limit
- grounded final-answer generation
- deterministic table extraction
- Pydantic structured responses
- `run_agent()` service layer
- mocked LangGraph workflow tests

### Phase 4 — Evaluation ✅

Completed:

- 60-question hand-checked evaluation suite
- 20 simple questions
- 15 joins and aggregations
- 10 multi-step questions
- 5 ambiguous questions
- 5 unanswerable questions
- 5 adversarial questions
- hand-written reference SQL for all 45 answerable cases
- semantic result-equivalence evaluation
- expected-table checks
- attempt-count and execution diagnostics
- infrastructure-error separation
- classifier evaluation
- evaluation-comparator regression tests
- analysis of initial benchmark failures
- evaluator corrections for false negatives
- iterative general prompt refinement for genuine semantic failures
- final post-refinement answerable benchmark: 45/45
- final classification benchmark: 15/15
- final regression suite: 60/60

### Phase 5 — Backend and frontend ✅

Completed:

- FastAPI application
- `/api/ask`
- `/health`
- Pydantic API request/response schemas
- request validation
- safe 429 and 500 handling
- CORS for local React development
- API request timing
- combined classification + first SQL planning
- cached schema context
- scalar-result deterministic fast path
- retained SQL repair path
- React + Vite frontend
- answer, SQL and execution views
- Markdown-rendered complex answers
- percentage-aware scalar answer formatting
- tables-used, attempts, row-count and timing metrics
- loading and error states
- FastAPI serving compiled React assets
- production-path regression evaluator
- final production regression: 60/60
- full Python suite: 41/41
- frontend lint validation
- frontend production build validation
- integrated FastAPI/React serving verification
- production logging cleanup
- explicit Groq SDK dependency pin

### Phase 6 — Docker and CI/CD

Next:

- multi-stage Docker image
- React build stage
- lean Python runtime image
- separation of runtime and development/data dependencies where practical
- PostgreSQL service container in GitHub Actions
- Python test workflow
- frontend lint/build validation
- mocked LLM tests in CI
- CI badge

### Phase 7 — Deployment and polish

Planned:

- full PostgreSQL database on Neon
- FastAPI + compiled React application on Render
- read-only production database credentials
- environment-based secrets
- public demo rate limiting
- answer caching
- public demo safeguards
- architecture diagram
- demo GIF/video
- final portfolio documentation

## Repository principles

The repository should never contain:

- `.env`
- database passwords
- Groq API keys
- production database URLs
- raw Olist CSV files

Safe examples and placeholders may be committed through `.env.example`.

The production agent must connect to PostgreSQL using read-only credentials.

## License and attribution

Dataset:

**Brazilian E-Commerce Public Dataset by Olist**

Kaggle identifier:

```text
olistbr/brazilian-ecommerce
```

The dataset page reports **CC BY-NC-SA 4.0**.

CommercePilot is being developed as a non-commercial personal portfolio project.

Dataset attribution, source information and relevant license information will remain visible in the public repository and demo.

The dataset license does not automatically define the license of CommercePilot's source code.

## Status

```text
Phase 0  ✅ Complete
Phase 1  ✅ Complete
Phase 2  ✅ Complete
Phase 3  ✅ Complete
Phase 4  ✅ Complete
Phase 5  ✅ Complete
Phase 6  ▶️ Next
Phase 7  ⬜
```

**Next step: Phase 6 — Docker and CI/CD.**
