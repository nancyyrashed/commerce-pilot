# CommercePilot Architecture

CommercePilot uses PostgreSQL throughout local development, testing, and production. The public demo runs as a single containerized application on Vercel, while the production database is hosted on Neon.

## Production architecture

```mermaid
flowchart TD
    User["User / Browser"]

    subgraph Vercel["Vercel Container"]
        React["React + Vite<br/>Compiled Frontend"]
        API["FastAPI<br/>/api/ask"]
        Safeguards["Public Demo Safeguards<br/>Per-instance Rate Limit<br/>Answer Cache"]
        Agent["LangGraph Agent"]
        Planner["Classification +<br/>Initial SQL Generation"]
        Validator["sqlglot<br/>SQL Validation"]
        Executor["Safe Query Execution"]
        Answer["Answer Generation"]
    end

    Groq["Groq LLM<br/>openai/gpt-oss-20b"]

    subgraph Neon["Neon PostgreSQL"]
        Reader["commercepilot_reader<br/>Read-only Role"]
        Database["Olist Database<br/>9 Tables"]
    end

    User --> React
    React --> API
    API --> Safeguards

    Safeguards -->|"Cache hit"| API
    Safeguards -->|"Cache miss"| Agent

    Agent --> Planner
    Planner <--> Groq

    Planner --> Validator
    Validator --> Executor

    Executor --> Reader
    Reader --> Database

    Executor -->|"Query error"| Agent
    Executor -->|"Query result"| Answer

    Answer <--> Groq
    Answer --> API
    API --> React
    React --> User
```

## Query execution safeguards

```mermaid
flowchart TD
    Question["Natural-language question"]
    Plan["Classify request + generate SQL"]
    Type{"Answerable?"}
    Validate["Parse and validate with sqlglot"]
    Safe{"Safe SELECT?"}
    Limit["Enforce maximum 100 rows"]
    Execute["Execute with commercepilot_reader"]
    Timeout["PostgreSQL 10-second statement timeout"]
    Success{"Execution successful?"}
    Retry{"Attempts < 3?"}
    Repair["Generate repaired SQL"]
    Result["Return grounded answer"]
    Direct["Clarify / Unanswerable / Reject"]

    Question --> Plan
    Plan --> Type

    Type -->|"No"| Direct
    Type -->|"Yes"| Validate

    Validate --> Safe
    Safe -->|"No"| Retry
    Safe -->|"Yes"| Limit

    Limit --> Execute
    Execute --> Timeout
    Timeout --> Success

    Success -->|"Yes"| Result
    Success -->|"No"| Retry

    Retry -->|"Yes"| Repair
    Repair --> Validate

    Retry -->|"No"| Result
```

## Production boundaries

The deployed application uses several independent safety layers:

- model-generated SQL is parsed and validated before execution
- only read-only query patterns are accepted
- result sets are capped at 100 rows
- PostgreSQL access uses the restricted `commercepilot_reader` role
- the reader role has a 10-second PostgreSQL statement timeout
- SQL repair is limited to a maximum of 3 generation attempts
- successful repeated questions can be served from an in-memory answer cache
- a lightweight per-instance request limiter protects the public portfolio demo
- secrets are provided through environment variables and are not committed to Git

The public-demo cache and request limiter are process-local. On a platform such as Vercel, multiple container instances may maintain independent in-memory state, so the limiter is intentionally described as a lightweight per-instance safeguard rather than a globally distributed rate limit.