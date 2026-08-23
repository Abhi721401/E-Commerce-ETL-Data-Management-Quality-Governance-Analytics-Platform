"""
test_transform.py
------------------
Unit tests for src/transform.py covering:
    - transformation correctness (business metrics, standardization)
    - row-count preservation where expected
    - business-aware handling of missingness (not blindly dropped)
    - geolocation deduplication rule
"""

import pandas as pd

from src.transform import (
    transform_customers,
    transform_geolocation,
    transform_order_items,
    transform_orders,
    transform_reviews,
)


def test_transform_customers_standardizes_casing():
    df = pd.DataFrame({
        "customer_id": ["c1"],
        "customer_unique_id": ["u1"],
        "customer_zip_code_prefix": [12345],
        "customer_city": ["  Sao Paulo "],
        "customer_state": ["sp"],
    })
    result = transform_customers(df)
    assert result.loc[0, "customer_city"] == "sao paulo"
    assert result.loc[0, "customer_state"] == "SP"


def test_transform_customers_preserves_row_count():
    df = pd.DataFrame({
        "customer_id": ["c1", "c2"],
        "customer_unique_id": ["u1", "u2"],
        "customer_zip_code_prefix": [1, 2],
        "customer_city": ["a", "b"],
        "customer_state": ["sp", "rj"],
    })
    assert len(transform_customers(df)) == len(df)


def test_transform_order_items_computes_total_item_value():
    df = pd.DataFrame({
        "order_id": ["o1"],
        "order_item_id": [1],
        "product_id": ["p1"],
        "seller_id": ["s1"],
        "shipping_limit_date": ["2024-01-01"],
        "price": [100.0],
        "freight_value": [15.0],
    })
    result = transform_order_items(df)
    assert result.loc[0, "total_item_value"] == 115.0


def test_transform_orders_flags_is_late_only_when_delivered():
    df = pd.DataFrame({
        "order_id": ["o1", "o2"],
        "customer_id": ["c1", "c2"],
        "order_status": ["delivered", "canceled"],
        "order_purchase_timestamp": ["2024-01-01", "2024-01-01"],
        "order_approved_at": ["2024-01-01", "2024-01-01"],
        "order_delivered_carrier_date": ["2024-01-02", None],
        "order_delivered_customer_date": ["2024-01-10", None],
        "order_estimated_delivery_date": ["2024-01-05", "2024-01-05"],
    })
    result = transform_orders(df)
    assert result.loc[0, "is_late"] == True  # delivered late
    assert pd.isna(result.loc[1, "is_late"])  # never delivered -> not applicable, not False


def test_transform_orders_does_not_drop_cancelled_rows_with_missing_dates():
    df = pd.DataFrame({
        "order_id": ["o1"],
        "customer_id": ["c1"],
        "order_status": ["canceled"],
        "order_purchase_timestamp": ["2024-01-01"],
        "order_approved_at": [None],
        "order_delivered_carrier_date": [None],
        "order_delivered_customer_date": [None],
        "order_estimated_delivery_date": ["2024-01-05"],
    })
    result = transform_orders(df)
    assert len(result) == 1  # row preserved despite multiple missing dates


def test_transform_reviews_preserves_optional_missing_text():
    df = pd.DataFrame({
        "review_id": ["r1"],
        "order_id": ["o1"],
        "review_score": [5],
        "review_comment_title": [None],
        "review_comment_message": [None],
        "review_creation_date": ["2024-01-01"],
        "review_answer_timestamp": ["2024-01-02"],
    })
    result = transform_reviews(df)
    assert len(result) == 1
    assert pd.isna(result.loc[0, "review_comment_title"])


def test_transform_geolocation_lookup_has_one_row_per_zip_prefix():
    df = pd.DataFrame({
        "geolocation_zip_code_prefix": [1001, 1001, 1002],
        "geolocation_lat": [-23.5, -23.6, -22.9],
        "geolocation_lng": [-46.6, -46.7, -43.2],
        "geolocation_city": ["sao paulo", "sao paulo", "rio de janeiro"],
        "geolocation_state": ["SP", "SP", "RJ"],
    })
    full, lookup = transform_geolocation(df)
    assert len(full) == 3          # raw-equivalent rows all preserved
    assert len(lookup) == 2        # deduplicated to one row per zip prefix
    assert lookup["geolocation_zip_code_prefix"].is_unique


def test_transform_geolocation_deduplication_is_deterministic():
    df = pd.DataFrame({
        "geolocation_zip_code_prefix": [1001, 1001],
        "geolocation_lat": [-23.6, -23.5],
        "geolocation_lng": [-46.7, -46.6],
        "geolocation_city": ["sao paulo", "sao paulo"],
        "geolocation_state": ["SP", "SP"],
    })
    _, lookup1 = transform_geolocation(df.copy())
    _, lookup2 = transform_geolocation(df.sample(frac=1, random_state=1).reset_index(drop=True))
    # Same deterministic result regardless of input row order
    assert lookup1["geolocation_lat"].iloc[0] == lookup2["geolocation_lat"].iloc[0]
