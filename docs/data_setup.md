# CommercePilot Dataset Setup

This document explains the one-time local setup required to load the full Brazilian E-Commerce Public Dataset by Olist into CommercePilot's PostgreSQL database.

The raw dataset is not committed to Git. A fresh clone therefore requires downloading the source CSV files before running the database loader.

## 1. Requirements

Install:

- Python 3.11
- Docker Desktop
- Git

The project uses PostgreSQL through Docker Compose.

## 2. Create the Python environment

From the CommercePilot project root:

```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## 3. Configure environment variables

Copy:

```text
.env.example
```

to:

```text
.env
```

Fill in the local PostgreSQL credentials.

The loader expects these environment variables:

```text
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_PORT
```

Keep `.env` private. It must never be committed to Git.

## 4. Download the Olist dataset

The project uses the **Brazilian E-Commerce Public Dataset by Olist** from Kaggle.

Dataset:

```text
olistbr/brazilian-ecommerce
```

The raw CSV files belong in:

```text
data/raw/
```

The expected files are:

```text
data/raw/
├── olist_customers_dataset.csv
├── olist_geolocation_dataset.csv
├── olist_orders_dataset.csv
├── olist_order_items_dataset.csv
├── olist_order_payments_dataset.csv
├── olist_order_reviews_dataset.csv
├── olist_products_dataset.csv
├── olist_sellers_dataset.csv
└── product_category_name_translation.csv
```

If the Kaggle CLI is configured, the dataset can be downloaded and extracted with:

```cmd
kaggle datasets download -d olistbr/brazilian-ecommerce -p data/raw --unzip
```

Alternatively, download the dataset manually from Kaggle and place the nine CSV files in `data/raw/`.

Raw dataset files are excluded from Git and should remain local.

## 5. Start PostgreSQL

Make sure Docker Desktop is running.

From the project root:

```cmd
docker compose up -d
```

Check that the database container is running:

```cmd
docker compose ps
```

The PostgreSQL service should show as running.

## 6. Verify the database connection

Run:

```cmd
python scripts/check_db.py
```

This confirms that Python can connect to the PostgreSQL instance using the environment configuration.

## 7. Load the full dataset

Run:

```cmd
python scripts/load_data.py
```

The loader:

- Reads all nine CSV files from `data/raw/`.
- Reads source values as text first to preserve identifiers.
- Validates source columns against the PostgreSQL schema.
- Converts values explicitly to the required PostgreSQL types.
- Preserves empty CSV fields as SQL `NULL`.
- Preserves monetary values using `Decimal`.
- Rejects invalid integer, monetary, coordinate, and timestamp values.
- Removes only exact duplicate rows from the geolocation dataset.
- Creates the PostgreSQL tables from `scripts/schema.sql`.
- Loads parent tables before dependent tables.
- Uses PostgreSQL `COPY` for efficient loading.
- Checks the number of loaded rows after every table.
- Runs the entire load in one transaction.

If any step fails, the transaction is rolled back.

The loader also refuses to append to or overwrite existing CommercePilot tables. It is intended to create a fresh dataset.

A successful run ends with:

```text
Success: all nine tables were loaded and committed.
```

## 8. Expected loaded tables

The full PostgreSQL database contains these nine data tables:

| Table | Expected rows |
| --- | ---: |
| `customers` | 99,441 |
| `sellers` | 3,095 |
| `product_category_name_translation` | 71 |
| `products` | 32,951 |
| `orders` | 99,441 |
| `order_items` | 112,650 |
| `order_payments` | 103,886 |
| `order_reviews` | 99,224 |
| `geolocation` | 738,332 |

The original geolocation CSV contains 1,000,163 rows. Exact duplicate removal leaves 738,332 loaded rows.

## 9. Create the read-only database role

CommercePilot's future SQL agent must never connect using the administrator account.

Create and verify the dedicated reader:

```cmd
python scripts/setup_readonly.py
```

The agent-facing PostgreSQL role is:

```text
commercepilot_reader
```

It must have read-only access to the project tables.

The setup has been verified to reject:

- `INSERT`
- `UPDATE`
- `DELETE`
- ordinary table creation
- temporary table creation

Administrator credentials are used only for setup and data loading.

## 10. Configure the query timeout

The public SQL agent generates queries dynamically, so the reader also has a PostgreSQL statement timeout.

Set it using the database administrator role:

```cmd
docker compose exec db psql -U commercepilot_admin -d commercepilot -c "ALTER ROLE commercepilot_reader SET statement_timeout = '10s';"
```

Verify it:

```cmd
docker compose exec db psql -U commercepilot_reader -d commercepilot -c "SHOW statement_timeout;"
```

Expected result:

```text
 statement_timeout
-------------------
 10s
(1 row)
```

This timeout applies only to PostgreSQL statements executed by `commercepilot_reader`. It does not limit the total time spent by the LLM or the complete CommercePilot request.

## 11. Verify read-only protection

Confirm that the reader can query the database:

```cmd
docker compose exec db psql -U commercepilot_reader -d commercepilot -c "SELECT COUNT(*) FROM orders;"
```

Expected result:

```text
99441
```

Then verify that it cannot create database objects:

```cmd
docker compose exec db psql -U commercepilot_reader -d commercepilot -c "CREATE TABLE phase1_write_test (id INT);"
```

Expected behavior:

```text
ERROR:  permission denied for schema public
```

That error is intentional and confirms that the role remains read-only.

## 12. Verify database size

To inspect the full database size:

```cmd
docker compose exec db psql -U commercepilot_reader -d commercepilot -c "SELECT pg_size_pretty(pg_database_size('commercepilot')) AS database_size;"
```

The Phase 1 database snapshot measured approximately:

```text
195 MB
```

This size includes the PostgreSQL database objects already present in the local database.

## 13. Dataset documentation

Detailed information about:

- table grains,
- column meanings,
- primary and foreign keys,
- missing values,
- date coverage,
- join traps,
- customer identity semantics,
- metric definitions,
- and cleaning decisions

is documented in:

```text
docs/data_dictionary.md
```

The data dictionary is the authoritative project reference for interpreting the loaded Olist data.

## 14. Important metric conventions

CommercePilot uses the following project convention:

```text
sales value = SUM(order_items.price)
```

Sales value excludes freight unless explicitly requested.

The project uses the term **sales value** rather than automatically describing this amount as accounting revenue.

When no order status is specified for a sales-value question, the project convention is to use delivered orders and state that assumption in the answer.

See `docs/data_dictionary.md` for the complete metric rules.

## 15. Rebuilding the database

`scripts/load_data.py` intentionally refuses to overwrite existing project tables.

If the database needs to be rebuilt, reset the development PostgreSQL environment deliberately before running the loader again.

Do not casually delete or recreate the database when existing development data needs to be preserved.

After resetting to an empty project database, repeat:

```cmd
docker compose up -d
python scripts/check_db.py
python scripts/load_data.py
python scripts/setup_readonly.py
```

Then configure and verify the reader's 10-second statement timeout.

## 16. Security and repository rules

Never commit:

```text
.env
data/raw/
database passwords
Groq API keys
production database URLs
```

The repository should contain only safe placeholders such as:

```text
.env.example
```

The public CommercePilot application must eventually connect using the restricted read-only role rather than the PostgreSQL administrator account.

## 17. Phase 1 completion criteria

The data phase is complete when:

- All nine source CSV files can be loaded through `scripts/load_data.py`.
- PostgreSQL contains the expected full dataset.
- Row counts have been verified.
- Schema relationships and data semantics are documented.
- `commercepilot_reader` can query all required tables.
- The reader cannot modify the database.
- `statement_timeout` is set to 10 seconds.
- Raw data and secrets remain outside Git.
- The one-time dataset setup is documented here.