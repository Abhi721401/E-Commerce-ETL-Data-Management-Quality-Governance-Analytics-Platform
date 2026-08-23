-- create_tables.sql
-- ---------------------------------------------------------------------
-- Star schema DDL for olist_analytics.
-- Run after create_database.sql. load.py (via SQLAlchemy) will create/
-- replace these tables automatically on each pipeline run, but this file
-- documents the intended schema explicitly and can be run manually to
-- pre-create tables with proper constraints/indexes before the first load.
-- ---------------------------------------------------------------------

\c olist_analytics

-- ============================================================
-- DIMENSION: dim_date
-- ============================================================
DROP TABLE IF EXISTS dim_date CASCADE;
CREATE TABLE dim_date (
    date_key      INTEGER PRIMARY KEY,          -- YYYYMMDD
    full_date     DATE NOT NULL,
    year          INTEGER NOT NULL,
    month         INTEGER NOT NULL,
    day           INTEGER NOT NULL,
    quarter       INTEGER NOT NULL,
    day_of_week   VARCHAR(20) NOT NULL,
    month_name    VARCHAR(20) NOT NULL
);

-- ============================================================
-- DIMENSION: dim_customer
-- ============================================================
DROP TABLE IF EXISTS dim_customer CASCADE;
CREATE TABLE dim_customer (
    customer_key             SERIAL PRIMARY KEY,
    customer_id               VARCHAR(64) NOT NULL UNIQUE,
    customer_unique_id         VARCHAR(64),
    customer_zip_code_prefix    INTEGER,
    customer_city               VARCHAR(100),
    customer_state               VARCHAR(2)
);
CREATE INDEX idx_dim_customer_state ON dim_customer (customer_state);

-- ============================================================
-- DIMENSION: dim_product
-- ============================================================
DROP TABLE IF EXISTS dim_product CASCADE;
CREATE TABLE dim_product (
    product_key                  SERIAL PRIMARY KEY,
    product_id                    VARCHAR(64) NOT NULL UNIQUE,
    product_category_name          VARCHAR(100),
    product_category_name_english   VARCHAR(100),
    product_name_lenght             NUMERIC,
    product_description_lenght       NUMERIC,
    product_photos_qty                NUMERIC,
    product_weight_g                   NUMERIC,
    product_length_cm                   NUMERIC,
    product_height_cm                    NUMERIC,
    product_width_cm                      NUMERIC
);
CREATE INDEX idx_dim_product_category ON dim_product (product_category_name_english);

-- ============================================================
-- DIMENSION: dim_seller
-- ============================================================
DROP TABLE IF EXISTS dim_seller CASCADE;
CREATE TABLE dim_seller (
    seller_key                SERIAL PRIMARY KEY,
    seller_id                  VARCHAR(64) NOT NULL UNIQUE,
    seller_zip_code_prefix       INTEGER,
    seller_city                   VARCHAR(100),
    seller_state                   VARCHAR(2)
);
CREATE INDEX idx_dim_seller_state ON dim_seller (seller_state);

-- ============================================================
-- DIMENSION: dim_location  (deduplicated zip-prefix geolocation lookup)
-- ============================================================
DROP TABLE IF EXISTS dim_location CASCADE;
CREATE TABLE dim_location (
    location_key                  SERIAL PRIMARY KEY,
    geolocation_zip_code_prefix     INTEGER NOT NULL UNIQUE,
    geolocation_lat                  NUMERIC,
    geolocation_lng                   NUMERIC,
    geolocation_city                   VARCHAR(100),
    geolocation_state                   VARCHAR(2)
);

-- ============================================================
-- FACT: fact_sales  (grain = one row per order item)
-- ============================================================
DROP TABLE IF EXISTS fact_sales CASCADE;
CREATE TABLE fact_sales (
    order_key         INTEGER,
    order_id            VARCHAR(64) NOT NULL,
    order_item_id         INTEGER NOT NULL,
    customer_key            INTEGER REFERENCES dim_customer (customer_key),
    product_key               INTEGER REFERENCES dim_product (product_key),
    seller_key                  INTEGER REFERENCES dim_seller (seller_key),
    date_key                       INTEGER REFERENCES dim_date (date_key),
    order_status                     VARCHAR(20),
    price                              NUMERIC(12, 2) NOT NULL,
    freight_value                       NUMERIC(12, 2) NOT NULL,
    total_value                          NUMERIC(12, 2) NOT NULL,
    PRIMARY KEY (order_id, order_item_id)
);
CREATE INDEX idx_fact_sales_customer ON fact_sales (customer_key);
CREATE INDEX idx_fact_sales_product ON fact_sales (product_key);
CREATE INDEX idx_fact_sales_seller ON fact_sales (seller_key);
CREATE INDEX idx_fact_sales_date ON fact_sales (date_key);

-- ============================================================
-- STAGING / GOVERNANCE TABLES
-- (raw-clean copies used for data-quality & governance reporting;
--  loaded by src/load.py as stg_<dataset>)
-- ============================================================
-- These are created dynamically by pandas.to_sql() in load.py, so no
-- explicit DDL is required here. They are documented for completeness:
--   stg_orders, stg_order_items, stg_payments, stg_reviews,
--   stg_products, stg_customers, stg_sellers
