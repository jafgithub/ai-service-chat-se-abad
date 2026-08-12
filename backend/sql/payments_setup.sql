-- Schema changes for payments. Re-runnable: apply it as many times as you like.
--
--     sudo mysql <dbname> < payments_setup.sql
--
-- Applied by hand, exactly like sync_setup.sql, because this project has no
-- migration tool. `Base.metadata.create_all` in app/main.py only ever emits
-- CREATE TABLE IF NOT EXISTS, so it creates the `payments` table on the next
-- restart but can never add a column or an index to a table that already
-- exists. Everything below is the part create_all cannot do.
--
-- Run this BEFORE deploying the payment code: the app assumes the unique keys
-- exist and relies on them to reject duplicates.

-- ---------------------------------------------------------------------------
-- 1. One customer per email address
-- ---------------------------------------------------------------------------
-- api/orders.py "upserts" a customer with SELECT-then-INSERT and no constraint
-- behind it, so two concurrent first-time orders from the same person create
-- two customer rows. That has already happened on dev. Deduplicate first, or
-- the unique index below cannot be created.

-- Point every order at the lowest-numbered customer row for its email.
UPDATE orders o
JOIN customers dup  ON dup.id = o.customer_id
JOIN (
    SELECT email, MIN(id) AS keep_id
    FROM customers
    GROUP BY email
) k ON k.email = dup.email
SET o.customer_id = k.keep_id
WHERE o.customer_id <> k.keep_id;

-- The sync maps local ids to remote ids; drop mappings for rows about to go so
-- a stale mapping can never point at a deleted customer.
DELETE m FROM sync_id_map m
JOIN customers dup ON dup.id = m.local_id
JOIN (
    SELECT email, MIN(id) AS keep_id
    FROM customers
    GROUP BY email
) k ON k.email = dup.email
WHERE m.table_name = 'customers' AND dup.id <> k.keep_id;

-- Now the duplicates are unreferenced.
DELETE dup FROM customers dup
JOIN (
    SELECT email, MIN(id) AS keep_id
    FROM customers
    GROUP BY email
) k ON k.email = dup.email
WHERE dup.id <> k.keep_id;

-- MySQL has no "ADD INDEX IF NOT EXISTS", so check information_schema first and
-- build the statement only when it is missing. Keeps the file re-runnable.
SET @have_email_uq := (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'customers'
      AND INDEX_NAME   = 'uq_customers_email'
);
SET @sql := IF(@have_email_uq = 0,
    'ALTER TABLE customers ADD UNIQUE KEY uq_customers_email (email)',
    'SELECT "uq_customers_email already present" AS note');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ---------------------------------------------------------------------------
-- 2. Idempotency key on orders
-- ---------------------------------------------------------------------------
-- Stops a double-clicked checkout, a retried request or a replayed payload from
-- creating a second order. NULL is allowed and MySQL permits many NULLs in a
-- unique index, so orders placed without a key still work.

SET @have_idem_col := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'orders'
      AND COLUMN_NAME  = 'idempotency_key'
);
SET @sql := IF(@have_idem_col = 0,
    'ALTER TABLE orders ADD COLUMN idempotency_key VARCHAR(64) NULL',
    'SELECT "orders.idempotency_key already present" AS note');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @have_idem_uq := (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'orders'
      AND INDEX_NAME   = 'uq_orders_idempotency_key'
);
SET @sql := IF(@have_idem_uq = 0,
    'ALTER TABLE orders ADD UNIQUE KEY uq_orders_idempotency_key (idempotency_key)',
    'SELECT "uq_orders_idempotency_key already present" AS note');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ---------------------------------------------------------------------------
-- 3. Payments
-- ---------------------------------------------------------------------------
-- create_all builds this too, from app/models/payment.py, but having it here
-- means the indexes are guaranteed and the table can be created before a deploy.
--
-- provider_event_id is the provider's own id for the event that last moved this
-- payment. It is unique because both Stripe and PayPal retry webhooks, and
-- replaying a delivery must never confirm an order or decrement stock twice.

CREATE TABLE IF NOT EXISTS payments (
    id                BIGINT       NOT NULL AUTO_INCREMENT,
    order_id          INT          NOT NULL,
    provider          VARCHAR(20)  NOT NULL,           -- stripe | paypal
    provider_ref      VARCHAR(255) NULL,               -- session / order id at the provider
    provider_event_id VARCHAR(255) NULL,               -- the webhook event already applied
    status            VARCHAR(20)  NOT NULL DEFAULT 'pending',
    amount            DECIMAL(10,2) NOT NULL DEFAULT 0,
    currency          VARCHAR(10)  NOT NULL DEFAULT 'USD',
    error_message     TEXT         NULL,
    created_at        DATETIME     NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME     NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_payments_event (provider_event_id),
    KEY ix_payments_order (order_id),
    KEY ix_payments_ref (provider, provider_ref)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Deliberately NOT done here: adding `payments` to the outbound sync.
-- ---------------------------------------------------------------------------
-- sync_to_remote.py computes shared_columns() at connection time, and
-- remote_db.py raises RuntimeError when a table is missing on the client's side.
-- That happens during connection setup, so registering a table the client does
-- not have would abort every pass and stall customers and orders too. Add the
-- trigger and the TABLES entry only after the client has created `payments`
-- remotely.


-- ---------------------------------------------------------------------------
-- Cash on delivery: how the customer is paying.
-- ---------------------------------------------------------------------------
-- Re-runnable: MySQL has no "ADD COLUMN IF NOT EXISTS", so this checks
-- information_schema and skips the ALTER when the column is already there.
--
-- This column stays LOCAL. sync_to_remote intersects the columns present on
-- both sides, so it is dropped silently on the way to the client. The order's
-- `notes` field carries the same information in words, and notes does sync,
-- which is what makes sure whoever delivers a cash order knows to collect.
SET @col := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'orders'
      AND COLUMN_NAME = 'payment_method'
);
SET @sql := IF(@col = 0,
    'ALTER TABLE orders ADD COLUMN payment_method VARCHAR(20) NULL',
    'SELECT ''orders.payment_method already present'' AS note');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT 'payments_setup.sql applied' AS result;
