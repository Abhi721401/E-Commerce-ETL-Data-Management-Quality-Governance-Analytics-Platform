"""
transform.py
------------
TRANSFORMATION layer.

Purpose:
    Clean and standardize each raw dataset while respecting the
    business-aware judgment calls documented in the project addendum:
      - Never blindly dropna() across a whole dataset.
      - Never blindly drop_duplicates() without first determining grain.
      - Missing review text is optional, not an error -> left as NULL.
      - Missing delivery dates are only suspicious for 'delivered' orders.
      - Missing product physical attributes are left as NULL, never 0.
      - Geolocation is deduplicated into an analytical lookup at the
        zip-prefix grain using a deterministic rule (first record per
        prefix after sorting), while the raw table itself is left intact
        upstream in data/raw/ (this module only ever reads raw data and
        writes to data/processed/).

    Every cleaning decision made here is written to a cleaning log
    (dataset, field, issue, business_reason, action, records_affected)
    for governance traceability.

Connects to:
    - extract.py    -> supplies raw DataFrames as input
    - config.py       -> PROCESSED_DATA_DIR, PROCESSED_FILES, CLEANING_LOG_PATH
    - load.py          -> loads the cleaned parquet outputs into PostgreSQL
    - reconciliation.py -> compares raw vs. transformed row counts
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.config import (
    CLEANING_LOG_PATH,
    NON_DELIVERY_STATUSES,
    PROCESSED_DATA_DIR,
    PROCESSED_FILES,
)
from src.logging_setup import get_logger

logger = get_logger(__name__)

_cleaning_log: list[dict[str, Any]] = []


def _log_action(dataset: str, field: str, issue: str, business_reason: str,
                 action: str, records_affected: int) -> None:
    _cleaning_log.append({
        "dataset": dataset,
        "field": field,
        "issue": issue,
        "business_reason": business_reason,
        "action": action,
        "records_affected": int(records_affected),
    })


DATE_COLUMNS = {
    "orders": [
        "order_purchase_timestamp", "order_approved_at",
        "order_delivered_carrier_date", "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "order_items": ["shipping_limit_date"],
    "reviews": ["review_creation_date", "review_answer_timestamp"],
}


def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def _convert_dates(df: pd.DataFrame, dataset: str) -> pd.DataFrame:
    df = df.copy()
    for col in DATE_COLUMNS.get(dataset, []):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def transform_customers(customers: pd.DataFrame) -> pd.DataFrame:
    df = _standardize_columns(customers)
    df["customer_city"] = df["customer_city"].str.strip().str.lower()
    df["customer_state"] = df["customer_state"].str.strip().str.upper()
    _log_action("customers", "customer_city/state", "inconsistent casing",
                "standardize text for consistent joins/reporting", "lowercased city / uppercased state", len(df))
    return df


def transform_sellers(sellers: pd.DataFrame) -> pd.DataFrame:
    df = _standardize_columns(sellers)
    df["seller_city"] = df["seller_city"].str.strip().str.lower()
    df["seller_state"] = df["seller_state"].str.strip().str.upper()
    return df


def transform_category_translation(category_translation: pd.DataFrame) -> pd.DataFrame:
    df = _standardize_columns(category_translation)
    df["product_category_name"] = df["product_category_name"].str.strip().str.lower()
    df["product_category_name_english"] = df["product_category_name_english"].str.strip().str.lower()
    return df


def transform_products(products: pd.DataFrame, category_translation: pd.DataFrame) -> pd.DataFrame:
    df = _standardize_columns(products)
    missing_category = df["product_category_name"].isnull().sum()
    _log_action(
        "products", "product_category_name", "missing category for some products",
        "legitimate — category not captured at listing time for all sellers; NOT deleted",
        "retain NULL; excluded from category-level revenue joins", missing_category,
    )

    for col in ["product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"]:
        missing = df[col].isnull().sum()
        if missing:
            _log_action(
                "products", col, "missing physical measurement",
                "NULL weight/dimension does not mean zero; imputing with 0 would corrupt "
                "freight/logistics analysis", "retain NULL (no imputation)", missing,
            )

    # Join English category name via the translation lookup (read-only join, raw untouched)
    df = df.merge(category_translation, on="product_category_name", how="left")
    unmatched_categories = df["product_category_name"].notnull() & df["product_category_name_english"].isnull()
    if unmatched_categories.sum():
        _log_action(
            "products", "product_category_name", "category not found in translation lookup",
            "category_translation reference table does not cover every raw category value",
            "retain original Portuguese name; english translation left NULL", int(unmatched_categories.sum()),
        )
    return df


def transform_orders(orders: pd.DataFrame) -> pd.DataFrame:
    df = _standardize_columns(orders)
    df = _convert_dates(df, "orders")
    df["order_status"] = df["order_status"].str.strip().str.lower()

    delivered_mask = df["order_status"] == "delivered"
    missing_delivered_date = delivered_mask & df["order_delivered_customer_date"].isnull()
    _log_action(
        "orders", "order_delivered_customer_date",
        "missing delivered_customer_date on a 'delivered'-status order",
        "unexpected — a delivered order should have a delivery timestamp; flagged as a true quality issue",
        "retain NULL, flagged in issue register (see DQ008)", int(missing_delivered_date.sum()),
    )

    non_delivery_mask = df["order_status"].isin(NON_DELIVERY_STATUSES) & df["order_delivered_customer_date"].isnull()
    _log_action(
        "orders", "order_delivered_customer_date",
        "missing delivered_customer_date on a non-delivered-status order",
        "expected business condition — cancelled/unavailable/etc. orders never reach delivery",
        "retain NULL; not treated as a quality defect", int(non_delivery_mask.sum()),
    )

    # --- Business metrics (STEP 8) -----------------------------------
    # delivery_days: calendar days from purchase to actual customer delivery
    df["delivery_days"] = (
        df["order_delivered_customer_date"] - df["order_purchase_timestamp"]
    ).dt.days

    # delivery_delay_days: actual delivery vs. estimated delivery date
    #   positive  -> delivered later than promised
    #   negative  -> delivered earlier than promised
    #   NaN        -> not yet delivered / not applicable
    df["delivery_delay_days"] = (
        df["order_delivered_customer_date"] - df["order_estimated_delivery_date"]
    ).dt.days

    # is_late: only meaningful for orders that actually have a delivery date.
    # Use pandas' nullable "boolean" dtype (not numpy bool) so that rows
    # without a delivery date can hold a true NA instead of being forced
    # into False, which would misrepresent "not yet delivered" as "on time".
    is_late = (df["delivery_delay_days"] > 0).astype("boolean")
    is_late[df["order_delivered_customer_date"].isnull()] = pd.NA
    df["is_late"] = is_late

    return df


def transform_order_items(order_items: pd.DataFrame) -> pd.DataFrame:
    df = _standardize_columns(order_items)
    df = _convert_dates(df, "order_items")
    df["total_item_value"] = df["price"] + df["freight_value"]
    return df


def transform_payments(payments: pd.DataFrame) -> pd.DataFrame:
    df = _standardize_columns(payments)
    df["payment_type"] = df["payment_type"].str.strip().str.lower()
    return df


def transform_reviews(reviews: pd.DataFrame) -> pd.DataFrame:
    df = _standardize_columns(reviews)
    df = _convert_dates(df, "reviews")
    missing_title = df["review_comment_title"].isnull().sum()
    missing_message = df["review_comment_message"].isnull().sum()
    _log_action(
        "reviews", "review_comment_title/message", "missing free-text review content",
        "review text is optional; a customer can submit a score without comments — NOT a quality defect",
        "retain NULL; excluded from mandatory completeness scoring", int(missing_title + missing_message),
    )
    return df


def transform_geolocation(geolocation: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns:
        (clean_full_table, zip_prefix_lookup)

    The raw geolocation table has ~26% duplicate full rows and many
    lat/lng observations per zip prefix (multiple deliveries/sensors
    reporting slightly different coordinates for the same prefix). We do
    NOT silently drop_duplicates() on the full table blindly — we first
    standardize text, then build a deterministic, documented analytical
    lookup at the zip_code_prefix grain for use as a dimension.
    """
    df = _standardize_columns(geolocation)
    df["geolocation_city"] = df["geolocation_city"].str.strip().str.lower()
    df["geolocation_state"] = df["geolocation_state"].str.strip().str.upper()

    full_duplicates = df.duplicated().sum()
    _log_action(
        "geolocation", "(all columns)", "large volume of full-row duplicates",
        "multiple raw geographic observations legitimately exist per zip prefix; "
        "the raw grain is observation-level, not entity-level",
        "retain all rows in the clean full table; deduplication only applied when "
        "building the zip_code_prefix analytical lookup", int(full_duplicates),
    )

    # Deterministic rule: for each zip prefix, take the first row after sorting
    # by (city, state, lat, lng) so the choice is reproducible, not arbitrary.
    lookup = (
        df.sort_values(["geolocation_zip_code_prefix", "geolocation_city",
                         "geolocation_state", "geolocation_lat", "geolocation_lng"])
          .drop_duplicates(subset=["geolocation_zip_code_prefix"], keep="first")
          .reset_index(drop=True)
    )
    _log_action(
        "geolocation", "geolocation_zip_code_prefix", "multiple lat/lng/city per zip prefix",
        "an analytical dimension requires one representative row per zip prefix",
        "built deterministic zip-prefix lookup: first row after sorting by "
        "(zip_prefix, city, state, lat, lng); documented, reproducible rule",
        int(len(df) - len(lookup)),
    )
    return df, lookup


def run_transformation(datasets: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """
    Run all dataset-specific transformations and write cleaned outputs to
    data/processed/. Returns the dict of transformed DataFrames (including
    the geolocation lookup) so downstream steps (quality scoring,
    reconciliation, load) can use them directly without re-reading disk.
    """
    global _cleaning_log
    _cleaning_log = []

    processed: dict[str, pd.DataFrame] = {}

    if "customers" in datasets:
        processed["customers"] = transform_customers(datasets["customers"])
    if "sellers" in datasets:
        processed["sellers"] = transform_sellers(datasets["sellers"])
    if "category_translation" in datasets:
        processed["category_translation"] = transform_category_translation(datasets["category_translation"])
    if "products" in datasets and "category_translation" in processed:
        processed["products"] = transform_products(datasets["products"], processed["category_translation"])
    elif "products" in datasets:
        processed["products"] = _standardize_columns(datasets["products"])
    if "orders" in datasets:
        processed["orders"] = transform_orders(datasets["orders"])
    if "order_items" in datasets:
        processed["order_items"] = transform_order_items(datasets["order_items"])
    if "payments" in datasets:
        processed["payments"] = transform_payments(datasets["payments"])
    if "reviews" in datasets:
        processed["reviews"] = transform_reviews(datasets["reviews"])
    if "geolocation" in datasets:
        geo_full, geo_lookup = transform_geolocation(datasets["geolocation"])
        processed["geolocation"] = geo_full
        processed["geolocation_lookup"] = geo_lookup

    # Persist processed outputs
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in processed.items():
        out_path = PROCESSED_DATA_DIR / PROCESSED_FILES.get(name, f"{name}_clean.parquet")
        df.to_parquet(out_path, index=False)
        logger.info("Wrote processed dataset '%s' -> %s (%d rows)", name, out_path.name, len(df))

    # Persist cleaning log
    log_df = pd.DataFrame(_cleaning_log)
    log_df.to_csv(CLEANING_LOG_PATH, index=False)
    logger.info("Cleaning log written to %s (%d entries)", CLEANING_LOG_PATH, len(log_df))

    return processed


def get_cleaning_log() -> pd.DataFrame:
    return pd.DataFrame(_cleaning_log)


if __name__ == "__main__":
    from src.extract import extract_all

    raw = extract_all()
    clean = run_transformation(raw)
    for name, df in clean.items():
        print(f"{name:>22s}: {len(df):>9,} rows")
