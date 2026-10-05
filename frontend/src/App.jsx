import { useState } from "react";
import ReactMarkdown from "react-markdown";

import { askCommercePilot } from "./api";
import "./App.css";


const EXAMPLE_QUESTIONS = [
  "How many orders are in the dataset?",
  "What were the top 5 product categories by sales value in 2018?",
  "What percentage of customers placed more than one order?",
];


function App() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("answer");
  const [copied, setCopied] = useState(false);


  async function submitQuestion(
    questionText,
  ) {
    const trimmedQuestion =
      questionText.trim();

    if (
      !trimmedQuestion
      || isLoading
    ) {
      return;
    }

    setIsLoading(true);
    setError("");
    setResult(null);
    setActiveTab("answer");
    setCopied(false);

    try {
      const data =
        await askCommercePilot(
          trimmedQuestion,
        );

      setResult(data);
    } catch (requestError) {
      setError(
        requestError.message
        || (
          "CommercePilot could not "
          + "process the request."
        ),
      );
    } finally {
      setIsLoading(false);
    }
  }


  async function handleSubmit(event) {
    event.preventDefault();

    await submitQuestion(
      question,
    );
  }


  async function handleExampleClick(
    example,
  ) {
    setQuestion(example);

    await submitQuestion(
      example,
    );
  }


  async function handleCopySql() {
    if (!result?.sql) {
      return;
    }

    try {
      await navigator.clipboard.writeText(
        result.sql,
      );

      setCopied(true);

      setTimeout(
        () => setCopied(false),
        1600,
      );
    } catch {
      setCopied(false);
    }
  }


  return (
    <main className="app-shell">

      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            CP
          </div>

          <div>
            <div className="brand-name">
              CommercePilot
            </div>

            <div className="brand-subtitle">
              AI Analytics Agent
            </div>
          </div>
        </div>

        <div className="system-status">
          <div className="status-dot" />

          <span>
            PostgreSQL · Read only
          </span>
        </div>
      </header>


      <section className="hero-panel">
        <div className="hero-copy">
          <div className="eyebrow">
            Natural language → SQL analytics
          </div>

          <h1>
            Ask your data.
            <span>
              Get grounded answers.
            </span>
          </h1>

          <p className="hero-description">
            CommercePilot turns business questions
            into validated PostgreSQL queries,
            executes them safely, and returns
            transparent analytics with the SQL
            behind every answer.
          </p>
        </div>

        <div className="dataset-panel">
          <div className="dataset-header">
            <span>
              Connected dataset
            </span>

            <span className="dataset-live">
              Dataset loaded
            </span>
          </div>

          <strong>
            Olist E-commerce
          </strong>

          <p>
            Historical Brazilian marketplace data
            across orders, customers, products,
            payments, sellers, and reviews.
          </p>

          <div className="dataset-stats">
            <div>
              <span>99K+</span>
              <small>Orders</small>
            </div>

            <div>
              <span>9</span>
              <small>Tables</small>
            </div>

            <div>
              <span>2016–18</span>
              <small>Period</small>
            </div>
          </div>
        </div>
      </section>


      <section className="query-workspace">
        <div className="section-heading">
          <div>
            <span className="section-kicker">
              Query workspace
            </span>

            <h2>
              What would you like to know?
            </h2>
          </div>

          <div className="query-mode">
            <span className="query-mode-dot" />
            Safe read-only mode
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="query-box">
            <textarea
              id="question"
              value={question}
              onChange={(event) =>
                setQuestion(
                  event.target.value,
                )
              }
              placeholder={
                "Ask a business question about "
                + "the Olist dataset..."
              }
              maxLength={500}
              rows={5}
              disabled={isLoading}
            />

            <div className="query-footer">
              <span className="character-count">
                {question.length}/500
              </span>

              <button
                type="submit"
                className="primary-button"
                disabled={
                  isLoading
                  || question.trim().length
                    === 0
                }
              >
                <span className="button-icon">
                  ✦
                </span>

                {isLoading
                  ? "Analyzing..."
                  : "Analyze data"}
              </button>
            </div>
          </div>
        </form>

        <div className="suggested-section">
          <span className="suggested-label">
            Suggested questions
          </span>

          <div className="example-buttons">
            {EXAMPLE_QUESTIONS.map(
              (example) => (
                <button
                  key={example}
                  type="button"
                  className="example-button"
                  disabled={isLoading}
                  onClick={() =>
                    handleExampleClick(
                      example,
                    )
                  }
                >
                  {example}
                </button>
              ),
            )}
          </div>
        </div>
      </section>


      {isLoading && (
        <section className="loading-panel">
          <div className="loading-top">
            <div className="loading-orb">
              <div />
            </div>

            <div>
              <span className="section-kicker">
                Agent working
              </span>

              <h2>
                Analyzing your question
              </h2>

              <p>
                CommercePilot is preparing a safe
                analytical query and checking the
                database result.
              </p>
            </div>
          </div>

          <div className="workflow-preview">
            <div className="workflow-step active">
              <span>01</span>
              Understand request
            </div>

            <div className="workflow-line" />

            <div className="workflow-step">
              <span>02</span>
              Generate SQL
            </div>

            <div className="workflow-line" />

            <div className="workflow-step">
              <span>03</span>
              Validate & execute
            </div>

            <div className="workflow-line" />

            <div className="workflow-step">
              <span>04</span>
              Return result
            </div>
          </div>
        </section>
      )}


      {error && (
        <section className="error-panel">
          <div className="error-icon">
            !
          </div>

          <div>
            <span className="section-kicker error">
              Request failed
            </span>

            <h2>
              CommercePilot could not complete
              the request
            </h2>

            <p>
              {error}
            </p>
          </div>
        </section>
      )}


      {result && (
        <section className="result-workspace">

          <div className="result-header">
            <div>
              <span className="section-kicker">
                Analysis result
              </span>

              <h2>
                CommercePilot response
              </h2>
            </div>

            <span
              className={
                result.success
                  ? "result-status success"
                  : "result-status error"
              }
            >
              <span />

              {result.success
                ? "Completed"
                : "Failed"}
            </span>
          </div>


          <div className="metrics-grid">
            <div className="metric-card">
              <span>
                Tables
              </span>

              <strong>
                {result.tables_used.length > 0
                  ? result.tables_used.join(", ")
                  : "None"}
              </strong>
            </div>

            <div className="metric-card">
              <span>
                Attempts
              </span>

              <strong>
                {result.attempts}
              </strong>
            </div>

            <div className="metric-card">
              <span>
                Rows returned
              </span>

              <strong>
                {result.row_count}
              </strong>
            </div>

            <div className="metric-card">
              <span>
                Execution time
              </span>

              <strong>
                {(
                  result.duration_ms
                  / 1000
                ).toFixed(2)}{" "}
                s
              </strong>
            </div>
          </div>


          <div className="result-tabs">
            <button
              type="button"
              className={
                activeTab === "answer"
                  ? "tab-button active"
                  : "tab-button"
              }
              onClick={() =>
                setActiveTab("answer")
              }
            >
              Answer
            </button>

            {result.sql && (
              <button
                type="button"
                className={
                  activeTab === "sql"
                    ? "tab-button active"
                    : "tab-button"
                }
                onClick={() =>
                  setActiveTab("sql")
                }
              >
                SQL
              </button>
            )}

            <button
              type="button"
              className={
                activeTab === "execution"
                  ? "tab-button active"
                  : "tab-button"
              }
              onClick={() =>
                setActiveTab("execution")
              }
            >
              Execution
            </button>
          </div>


          <div className="result-content">

            {activeTab === "answer" && (
              <div className="answer-panel">
                <div className="answer-icon">
                  ✦
                </div>

                <div>
                  <span className="content-label">
                    Answer
                  </span>

                  <div className="answer-text">
                    <ReactMarkdown>
                      {result.answer}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>
            )}


            {activeTab === "sql"
              && result.sql && (
                <div className="sql-panel">
                  <div className="sql-toolbar">
                    <div>
                      <span className="content-label">
                        Executed PostgreSQL
                      </span>
                    </div>

                    <button
                      type="button"
                      className="copy-button"
                      onClick={
                        handleCopySql
                      }
                    >
                      {copied
                        ? "Copied"
                        : "Copy SQL"}
                    </button>
                  </div>

                  <pre>
                    <code>
                      {result.sql}
                    </code>
                  </pre>
                </div>
              )}


            {activeTab === "execution" && (
              <div className="execution-panel">

                <div className="execution-row">
                  <span>
                    Status
                  </span>

                  <strong>
                    {result.success
                      ? "Successful"
                      : "Failed"}
                  </strong>
                </div>

                <div className="execution-row">
                  <span>
                    SQL attempts
                  </span>

                  <strong>
                    {result.attempts}
                  </strong>
                </div>

                <div className="execution-row">
                  <span>
                    Rows returned
                  </span>

                  <strong>
                    {result.row_count}
                  </strong>
                </div>

                <div className="execution-row">
                  <span>
                    Tables used
                  </span>

                  <strong>
                    {result.tables_used.length > 0
                      ? result.tables_used.join(
                        ", ",
                      )
                      : "None"}
                  </strong>
                </div>

                <div className="execution-row">
                  <span>
                    Duration
                  </span>

                  <strong>
                    {(
                      result.duration_ms
                      / 1000
                    ).toFixed(2)}{" "}
                    seconds
                  </strong>
                </div>

                {!result.success
                  && result.error && (
                    <div className="execution-error">
                      {result.error}
                    </div>
                  )}
              </div>
            )}

          </div>
        </section>
      )}


      <footer>
        <span>
          CommercePilot
        </span>

        <span>
          FastAPI · LangGraph · PostgreSQL
        </span>
      </footer>

    </main>
  );
}


export default App;