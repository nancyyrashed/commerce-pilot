-- ---------------------------------------------------------
-- CommercePilot CI database seed
-- ---------------------------------------------------------
-- This file creates the restricted reader role used by the
-- application tests and inserts a very small synthetic dataset.
--
-- It is only for GitHub Actions CI. It does not replace or
-- modify the real Olist dataset used locally or in production.
-- ---------------------------------------------------------


-- Create the same restricted reader role used by CommercePilot.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'commercepilot_reader'
    ) THEN
        CREATE ROLE commercepilot_reader
            LOGIN
            PASSWORD 'ci_reader_password'
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE;
    END IF;
END
$$;


-- Keep CI queries bounded just like the local reader account.
ALTER ROLE commercepilot_reader
SET statement_timeout = '10s';


-- ---------------------------------------------------------
-- Minimal customer fixture
-- ---------------------------------------------------------

INSERT INTO customers (
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix,
    customer_city,
    customer_state
)
SELECT
    'customer_' || LPAD(number::TEXT, 3, '0'),
    'unique_' || LPAD(number::TEXT, 3, '0'),
    '01001',
    'sao paulo',
    'SP'
FROM generate_series(1, 100) AS number;


-- ---------------------------------------------------------
-- Minimal order fixture
-- ---------------------------------------------------------
-- 100 rows are required because one integration test verifies
-- that CommercePilot's automatic LIMIT 100 is enforced.
-- ---------------------------------------------------------

INSERT INTO orders (
    order_id,
    customer_id,
    order_status,
    order_purchase_timestamp,
    order_approved_at,
    order_delivered_carrier_date,
    order_delivered_customer_date,
    order_estimated_delivery_date
)
SELECT
    'order_' || LPAD(number::TEXT, 3, '0'),
    'customer_' || LPAD(number::TEXT, 3, '0'),
    CASE
        WHEN number <= 90 THEN 'delivered'
        ELSE 'shipped'
    END,
    TIMESTAMP '2018-01-01 10:00:00'
        + ((number - 1) * INTERVAL '1 day'),
    TIMESTAMP '2018-01-01 11:00:00'
        + ((number - 1) * INTERVAL '1 day'),
    TIMESTAMP '2018-01-02 10:00:00'
        + ((number - 1) * INTERVAL '1 day'),
    CASE
        WHEN number <= 90 THEN
            TIMESTAMP '2018-01-05 10:00:00'
                + ((number - 1) * INTERVAL '1 day')
        ELSE NULL
    END,
    TIMESTAMP '2018-01-10 10:00:00'
        + ((number - 1) * INTERVAL '1 day')
FROM generate_series(1, 100) AS number;


-- ---------------------------------------------------------
-- Read-only permissions
-- ---------------------------------------------------------

GRANT CONNECT
ON DATABASE commercepilot
TO commercepilot_reader;

GRANT USAGE
ON SCHEMA public
TO commercepilot_reader;

GRANT SELECT
ON ALL TABLES IN SCHEMA public
TO commercepilot_reader;

GRANT SELECT
ON ALL SEQUENCES IN SCHEMA public
TO commercepilot_reader;