# CommercePilot Data Dictionary

Verified local dataset snapshot: 1 October 2026. This document describes the full PostgreSQL dataset loaded during Phase 1 and used by CommercePilot in both local development and the public demo.

## 1. Source and attribution

- **Creator:** Olist.
- **Dataset:** [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
- **Kaggle identifier:** `olistbr/brazilian-ecommerce`.
- **License:** [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/), confirmed from the dataset page during setup.
- **Modifications:** PostgreSQL table creation; explicit type conversion; empty CSV fields represented as SQL `NULL`; removal of exact duplicate geolocation rows; addition of a generated geolocation row identifier. Original CSV files are retained unchanged locally and excluded from Git.

The public CommercePilot demo uses the full PostgreSQL dataset. Appropriate attribution, a source link, the license link and a description of modifications must remain visible, and the project must comply with the applicable non-commercial and share-alike conditions. This dataset license is not a declaration of the project's software license.

Counts, key checks, lookup coverage, timestamps and status totals below come from the project's inspection scripts and database queries. Column descriptions explain the fields used in the project; a name alone does not establish every upstream business rule. In particular, source timezone and currency metadata have not been independently verified in this setup. Preserve source timestamps and amounts without conversion or an unverified display label.

## 2. Scope and time coverage

| Property | Verified value |
| --- | --- |
| Orders | 99,441 |
| Distinct customer identities (`customer_unique_id`) | 96,096 |
| Earliest purchase timestamp | `2016-09-04 21:15:19` |
| Latest purchase timestamp | `2018-10-17 17:30:18` |
| Source CSV files / loaded data tables | 9 / 9 |

These endpoints describe `orders.order_purchase_timestamp`, not the range of delivery, shipping, payment or review events. The first and last years are partial; being between the endpoints does not establish complete coverage for every day or month.

Use explicit historical periods. If someone asks about “this year” or “last month,” explain the available coverage and ask for an appropriate period rather than silently substituting a historical date. Timestamps are stored as `TIMESTAMP WITHOUT TIME ZONE`; no UTC conversion was applied.

### Order statuses

These are the status values in the loaded snapshot, not a history of status transitions.

| `order_status` | Orders |
| --- | ---: |
| `delivered` | 96,478 |
| `shipped` | 1,107 |
| `canceled` | 625 |
| `unavailable` | 609 |
| `invoiced` | 314 |
| `processing` | 301 |
| `created` | 5 |
| `approved` | 2 |
| **Total** | **99,441** |

Use exact stored spellings, including `canceled`.

## 3. Project metric definitions

These are CommercePilot conventions to implement in the agent and evaluation, not additional claims made by the source dataset.

| Metric | Definition and scope |
| --- | --- |
| Sales value | `SUM(order_items.price)` for the selected order cohort. Excludes `freight_value`. Default to orders whose status is `delivered` when no status is specified, and state that assumption in the answer. Honor an explicit different status filter. |
| Freight value | `SUM(order_items.freight_value)` over the selected item rows. Report separately from sales value. |
| Payment value | `SUM(order_payments.payment_value)` over the selected payment rows. Do not substitute it for item sales value or multiply it by `payment_installments`. |
| Order count | Count rows in `orders` for the requested cohort. An unqualified total order count includes all statuses. After a one-to-many join, use the appropriate distinct order count or aggregate before joining. |
| Item count | Count `order_items` rows for the selected cohort. Do not sum `order_item_id`: it is an item sequence number, not a quantity field. |
| Distinct customers | Count distinct `customer_unique_id` values. For a filtered order cohort, join the selected orders to customers before counting. |
| Repeat customers | Customer identities with at least two distinct orders in the explicitly stated period and status cohort. Do not infer this from repeated `customer_id` values. |

Use purchase time for sales and purchase trends unless the question specifies another event. Use actual customer-delivery time for delivery-date questions. Clearly state the date field, time window and status filter used.

Use “sales value,” not accounting “revenue,” profit or net income. Costs, fees, refunds and revenue-recognition rules have not been established by this model. Ask for clarification when a requested metric has no defined meaning here.

For calendar periods, prefer inclusive starts and exclusive ends: `timestamp >= '2017-01-01' AND timestamp < '2018-01-01'`. Avoid an end-of-day assumption that could exclude timestamps.

## 4. Table inventory and grain

**Grain** means what a single row represents. A primary key (PK) uniquely identifies a row; a foreign key (FK) requires a matching referenced record.

| Table | Loaded rows | Grain | Primary key |
| --- | ---: | --- | --- |
| `customers` | 99,441 | Customer record associated with an order | `customer_id` |
| `sellers` | 3,095 | Seller | `seller_id` |
| `product_category_name_translation` | 71 | Portuguese-to-English category mapping | `product_category_name` |
| `products` | 32,951 | Product | `product_id` |
| `orders` | 99,441 | Order | `order_id` |
| `order_items` | 112,650 | Item within an order | (`order_id`, `order_item_id`) |
| `order_payments` | 103,886 | Payment record within an order | (`order_id`, `payment_sequential`) |
| `order_reviews` | 99,224 | Review/order pair | (`review_id`, `order_id`) |
| `geolocation` | 738,332 | Distinct source location row after exact deduplication | `geolocation_id` (generated) |

### customers

Source: `olist_customers_dataset.csv`.

| Column | PostgreSQL type | Nullable | Meaning |
| --- | --- | --- | --- |
| `customer_id` | TEXT | No; PK | Customer record identifier used to join to `orders`. |
| `customer_unique_id` | TEXT | No | Customer identity across orders; use for distinct-customer and repeat-purchase analysis. |
| `customer_zip_code_prefix` | TEXT | No | Customer postal-code prefix; preserve leading zeros. |
| `customer_city` | TEXT | No | Recorded customer city. |
| `customer_state` | TEXT | No | Recorded customer state code. |

### sellers

Source: `olist_sellers_dataset.csv`.

| Column | PostgreSQL type | Nullable | Meaning |
| --- | --- | --- | --- |
| `seller_id` | TEXT | No; PK | Seller identifier. |
| `seller_zip_code_prefix` | TEXT | No | Seller postal-code prefix; preserve leading zeros. |
| `seller_city` | TEXT | No | Recorded seller city. |
| `seller_state` | TEXT | No | Recorded seller state code. |

### product_category_name_translation

Source: `product_category_name_translation.csv`.

| Column | PostgreSQL type | Nullable | Meaning |
| --- | --- | --- | --- |
| `product_category_name` | TEXT | No; PK | Portuguese category label. |
| `product_category_name_english` | TEXT | No | Corresponding English label supplied by the source. |

### products

Source: `olist_products_dataset.csv`. The original `lenght` spellings are intentionally preserved. Full product names and descriptions are not present in these columns.

| Column | PostgreSQL type | Nullable | Meaning |
| --- | --- | --- | --- |
| `product_id` | TEXT | No; PK | Product identifier. |
| `product_category_name` | TEXT | Yes | Portuguese category label; translation coverage is incomplete. |
| `product_name_lenght` | INTEGER | Yes | Source-reported length of the product name. |
| `product_description_lenght` | INTEGER | Yes | Source-reported length of the product description. |
| `product_photos_qty` | INTEGER | Yes | Recorded number of product photos. |
| `product_weight_g` | INTEGER | Yes | Product weight in grams. |
| `product_length_cm` | INTEGER | Yes | Product length in centimetres. |
| `product_height_cm` | INTEGER | Yes | Product height in centimetres. |
| `product_width_cm` | INTEGER | Yes | Product width in centimetres. |

### orders

Source: `olist_orders_dataset.csv`.

| Column | PostgreSQL type | Nullable | Meaning |
| --- | --- | --- | --- |
| `order_id` | TEXT | No; PK | Order identifier. |
| `customer_id` | TEXT | No; FK | Reference to `customers.customer_id`. |
| `order_status` | TEXT | No | Recorded order status in this snapshot. |
| `order_purchase_timestamp` | TIMESTAMP | No | Purchase timestamp; default time axis for sales and purchase trends. |
| `order_approved_at` | TIMESTAMP | Yes | Recorded approval timestamp. |
| `order_delivered_carrier_date` | TIMESTAMP | Yes | Recorded handover/delivery to the carrier; distinct from customer delivery. |
| `order_delivered_customer_date` | TIMESTAMP | Yes | Recorded actual customer-delivery timestamp. |
| `order_estimated_delivery_date` | TIMESTAMP | No | Recorded estimated customer-delivery date. |

For delivery duration or lateness, state the chosen definition and use rows with the required timestamps. Report exclusions. A missing delivery timestamp is not a zero-day delivery and does not by itself prove a cancellation.

### order_items

Source: `olist_order_items_dataset.csv`.

| Column | PostgreSQL type | Nullable | Meaning |
| --- | --- | --- | --- |
| `order_id` | TEXT | No; PK part, FK | Reference to `orders.order_id`. |
| `order_item_id` | INTEGER | No; PK part | Item sequence number within the order; not globally unique. |
| `product_id` | TEXT | No; FK | Reference to `products.product_id`. |
| `seller_id` | TEXT | No; FK | Reference to `sellers.seller_id`; one order can involve several sellers. |
| `shipping_limit_date` | TIMESTAMP | No | Recorded shipping deadline for the item; not actual shipment or delivery time. |
| `price` | NUMERIC(12, 2) | No | Item price used in CommercePilot's sales-value metric. |
| `freight_value` | NUMERIC(12, 2) | No | Freight amount recorded for the item; kept separate from item price. |

### order_payments

Source: `olist_order_payments_dataset.csv`.

| Column | PostgreSQL type | Nullable | Meaning |
| --- | --- | --- | --- |
| `order_id` | TEXT | No; PK part, FK | Reference to `orders.order_id`. |
| `payment_sequential` | INTEGER | No; PK part | Distinguishes payment records within an order. |
| `payment_type` | TEXT | No | Payment-method label recorded by the source. |
| `payment_installments` | INTEGER | No | Recorded installment count; not a multiplier for payment value. |
| `payment_value` | NUMERIC(12, 2) | No | Amount of this payment record. |

An order can have several payment records. This table has no payment timestamp, so do not claim that grouping it by order purchase time gives the date cash was received.

### order_reviews

Source: `olist_order_reviews_dataset.csv`.

| Column | PostgreSQL type | Nullable | Meaning |
| --- | --- | --- | --- |
| `review_id` | TEXT | No; PK part | Source review identifier; not unique by itself. |
| `order_id` | TEXT | No; PK part, FK | Reference to `orders.order_id`. |
| `review_score` | INTEGER | No | Recorded review score. |
| `review_comment_title` | TEXT | Yes | Optional written review title. |
| `review_comment_message` | TEXT | Yes | Optional written review message. |
| `review_creation_date` | TIMESTAMP | No | Source review-creation timestamp; do not substitute it for the answer timestamp. |
| `review_answer_timestamp` | TIMESTAMP | No | Recorded review-answer timestamp. |

There are 814 repeated `review_id` occurrences beyond the first, but no duplicate (`review_id`, `order_id`) pairs. No reviews were dropped. Do not assume one review row per order; define how to aggregate multiple reviews before using an order-level rating. Reviews are linked to orders, not uniquely to a product or seller in a multi-item order.

### geolocation

Source: `olist_geolocation_dataset.csv`; the generated ID is not a source field.

| Column | PostgreSQL type | Nullable | Meaning |
| --- | --- | --- | --- |
| `geolocation_id` | BIGINT identity | No; PK | Generated identifier for the loaded row; not a business identifier or a stable cross-export key. |
| `geolocation_zip_code_prefix` | TEXT | No | Postal prefix, shared by multiple location rows. |
| `geolocation_lat` | DOUBLE PRECISION | No | Recorded latitude coordinate. |
| `geolocation_lng` | DOUBLE PRECISION | No | Recorded longitude coordinate. |
| `geolocation_city` | TEXT | No | Recorded city label. |
| `geolocation_state` | TEXT | No | Recorded state code. |

The source contained 1,000,163 rows. Removing 261,831 exact duplicates left 738,332 rows and 19,015 distinct postal prefixes. Repeated prefixes remain legitimate separate location rows. No representative-coordinate rule has been implemented yet. A prefix-level coordinate would be an approximation, not a customer's exact address.

## 5. Relationships and join rules

The following six foreign keys are enforced. Inspection found zero missing source values and zero unmatched references for each.

| Referencing column | Referenced column |
| --- | --- |
| `orders.customer_id` | `customers.customer_id` |
| `order_items.order_id` | `orders.order_id` |
| `order_items.product_id` | `products.product_id` |
| `order_items.seller_id` | `sellers.seller_id` |
| `order_payments.order_id` | `orders.order_id` |
| `order_reviews.order_id` | `orders.order_id` |

A complete child-to-parent match does not prove that every parent has a child. For example, these checks do not prove that every order has an item, payment or review.

Category and postal-prefix lookups are not enforced as foreign keys:

| Lookup | Coverage limitation |
| --- | --- |
| Product category to translation | 610 products have a missing category; another 13 products use two untranslated categories: `pc_gamer` and `portateis_cozinha_e_preparadores_de_alimentos`. |
| Customer postal prefix to geolocation | 278 customer rows have unmatched prefixes, covering 157 distinct prefixes. |
| Seller postal prefix to geolocation | 7 seller rows have unmatched prefixes, covering 7 distinct prefixes. |

Use a left join when unmatched records must remain in the result. For display, retain the Portuguese category when its English translation is unavailable, and use a distinct “Unknown category” label for a missing source category. Do not write display fallback labels into the original source fields or invent translations.

Avoid multiplying rows:

- Joining items to payments on order ID creates every matching item/payment combination. Aggregate each table to one row per order first when comparing their totals.
- Joining reviews to items can repeat item prices. Aggregate reviews to the required grain first, or avoid that join when it is unnecessary.
- Never join raw geolocation rows to transactional data and then sum prices. First define a one-row-per-prefix lookup, or use `EXISTS` for a membership check. Customer/seller state questions can normally use their own state columns directly.
- A left join retains unmatched records but does not prevent row multiplication when the lookup key is not unique.
- `SUM(DISTINCT price)` is not a general fix for duplicated joins: different legitimate items may have the same price.

## 6. Missing values and cleaning decisions

| Table | Column(s) | Missing source values |
| --- | --- | ---: |
| `order_reviews` | `review_comment_title` | 87,656 |
| `order_reviews` | `review_comment_message` | 58,247 |
| `orders` | `order_approved_at` | 160 |
| `orders` | `order_delivered_carrier_date` | 1,783 |
| `orders` | `order_delivered_customer_date` | 2,965 |
| `products` | `product_category_name`, `product_name_lenght`, `product_description_lenght`, `product_photos_qty` | 610 per column |
| `products` | `product_weight_g`, `product_length_cm`, `product_height_cm`, `product_width_cm` | 2 per column |

All other inspected source columns had no empty-field missing values. These counts use the loader's parsing rule: empty fields are missing; literal strings such as `NA` or `NULL` are preserved. Whitespace-only strings are not automatically treated as missing. Per-column missing counts do not prove identical affected-row sets.

Cleaning preserves nulls, original identifiers, postal leading zeros, category labels and source column spellings. There is no blanket missing-row deletion, mean imputation, zero filling, review deduplication or guessed timestamp replacement. Only exact geolocation rows are deduplicated. Integer conversion rejects fractional values; monetary conversion rejects extra precision beyond two decimals; date parsing rejects invalid values. PostgreSQL enforces declared types, keys and required values during loading.

## 7. Example metric queries

### Delivered-order sales value for purchases in 2017

```sql
SELECT SUM(i.price) AS sales_value
FROM orders AS o
JOIN order_items AS i ON i.order_id = o.order_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2017-01-01'
  AND o.order_purchase_timestamp < '2018-01-01';
```

This adds item prices once per item and excludes freight. It uses purchase time and delivered status explicitly. A missing aggregate result must be distinguished from a measured zero according to the answer's context.

### Distinct customers with delivered purchases in 2017

```sql
SELECT COUNT(DISTINCT c.customer_unique_id) AS distinct_customers
FROM orders AS o
JOIN customers AS c ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2017-01-01'
  AND o.order_purchase_timestamp < '2018-01-01';
```

These examples define query semantics; their numerical results have not been recorded in this document.

## 8. Access, reproducibility and remaining work

- `scripts/schema.sql` defines the PostgreSQL tables.
- `scripts/load_data.py` creates and loads all nine tables in one transaction, checks row counts, and refuses to overwrite existing project tables.
- `scripts/setup_readonly.py` creates the dedicated reader and tests permissions. Its creation step refuses to change an existing role.
- `commercepilot_reader` successfully read all nine tables. Tests confirmed rejection of `INSERT`, `UPDATE`, `DELETE`, ordinary table creation and temporary table creation.
- `commercepilot_reader` has a PostgreSQL `statement_timeout` of 10 seconds. PostgreSQL automatically cancels a statement executed by this role if it exceeds that limit.
- The future SQL execution tool must connect as the reader. Administrator credentials are for setup and loading, not agent-generated queries.
- SQL validation and hard row-limit enforcement remain Phase 2 work.
- Raw data and credentials remain outside Git. Keep `.env.example` placeholders only.
- Before Phase 4 evaluation, record whether the agent receives this dictionary. Apply the same documented metric rules to hand-checked reference SQL and disclose that setup with the results.

Update this document when the schema, cleaning rules, database deployment architecture or metric definitions change. Keep the verified full-dataset counts synchronized with the PostgreSQL database.