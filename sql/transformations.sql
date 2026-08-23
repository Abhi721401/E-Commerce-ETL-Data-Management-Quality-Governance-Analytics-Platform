-- transformations.sql
-- ---------------------------------------------------------------------
-- Documents (in SQL) the same business logic implemented in
-- src/transform.py, for reviewers who want to see the transformation
-- rules expressed declaratively / for use if the pipeline is ever
-- re-implemented as SQL-based ELT (e.g. in PostgreSQL / dbt) instead of
-- pandas.
-- ---------------------------------------------------------------------

\c olist_analytics

-- ============================================================
-- View: orders with business metrics (delivery_days, delivery_delay_days, is_late)
-- ============================================================
CREATE OR REPLACE VIEW vw_orders_with_metrics AS
SELECT
    o.*,
    EXTRACT(DAY FROM (order_delivered_customer_date - order_purchase_timestamp))::INT
        AS delivery_days,
    EXTRACT(DAY FROM (order_delivered_customer_date - order_estimated_delivery_date))::INT
        AS delivery_delay_days,
    CASE
        WHEN order_delivered_customer_date IS NULL THEN NULL
        WHEN order_delivered_customer_date > order_estimated_delivery_date THEN TRUE
        ELSE FALSE
    END AS is_late
FROM stg_orders o;

-- ============================================================
-- View: conditional missingness check for delivery date
--   Mirrors DQ008 — only flags missing delivery date when status = 'delivered'
-- ============================================================
CREATE OR REPLACE VIEW vw_orders_missing_delivery_flagged AS
SELECT
    order_id,
    order_status,
    order_delivered_customer_date,
    CASE
        WHEN order_status = 'delivered' AND order_delivered_customer_date IS NULL
            THEN TRUE
        ELSE FALSE
    END AS is_true_quality_issue,
    CASE
        WHEN order_status != 'delivered' AND order_delivered_customer_date IS NULL
            THEN TRUE
        ELSE FALSE
    END AS is_expected_missingness
FROM stg_orders;

-- ============================================================
-- View: geolocation deduplicated lookup (mirrors transform_geolocation)
--   Deterministic rule: first row per zip prefix after sorting.
-- ============================================================
CREATE OR REPLACE VIEW vw_geolocation_lookup AS
SELECT DISTINCT ON (geolocation_zip_code_prefix)
    geolocation_zip_code_prefix,
    geolocation_lat,
    geolocation_lng,
    geolocation_city,
    geolocation_state
FROM stg_geolocation
ORDER BY geolocation_zip_code_prefix, geolocation_city, geolocation_state,
         geolocation_lat, geolocation_lng;

-- ============================================================
-- View: products joined to English category name
-- ============================================================
CREATE OR REPLACE VIEW vw_products_translated AS
SELECT
    p.*,
    c.product_category_name_english
FROM stg_products p
LEFT JOIN stg_category_translation c
    ON p.product_category_name = c.product_category_name;
