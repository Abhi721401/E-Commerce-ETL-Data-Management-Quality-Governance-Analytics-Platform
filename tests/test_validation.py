"""
test_validation.py
-------------------
Unit tests for src/validation.py covering:
    - duplicate detection (uniqueness)
    - null validation (completeness)
    - invalid values (validity)
    - referential integrity
    - date logic (timeliness)
    - conditional missingness
Includes both positive (rule passes) and negative (rule fails) cases.
"""

import pandas as pd
import pytest

from src.validation import (
    check_categorical_set,
    check_composite_unique,
    check_conditional_not_null,
    check_date_order,
    check_min_value,
    check_min_value_exclusive_optional,
    check_not_null,
    check_range,
    check_referential_integrity,
    check_unique,
)


# --- completeness ---------------------------------------------------

def test_not_null_passes_when_no_nulls():
    df = pd.DataFrame({"order_id": ["a", "b", "c"]})
    assert check_not_null(df, "order_id") == 0


def test_not_null_flags_nulls():
    df = pd.DataFrame({"order_id": ["a", None, "c"]})
    assert check_not_null(df, "order_id") == 1


# --- uniqueness ------------------------------------------------------

def test_unique_passes_with_no_duplicates():
    df = pd.DataFrame({"order_id": ["a", "b", "c"]})
    assert check_unique(df, "order_id") == 0


def test_unique_flags_duplicates():
    df = pd.DataFrame({"order_id": ["a", "a", "b"]})
    assert check_unique(df, "order_id") == 2  # both occurrences flagged


def test_composite_unique_allows_repeated_order_id_with_distinct_item_id():
    df = pd.DataFrame({
        "order_id": ["o1", "o1", "o2"],
        "order_item_id": [1, 2, 1],
    })
    assert check_composite_unique(df, "order_id", "order_item_id") == 0


def test_composite_unique_flags_true_duplicate_pair():
    df = pd.DataFrame({
        "order_id": ["o1", "o1", "o2"],
        "order_item_id": [1, 1, 1],
    })
    assert check_composite_unique(df, "order_id", "order_item_id") == 2


# --- validity ----------------------------------------------------------

def test_min_value_flags_negative_freight():
    df = pd.DataFrame({"freight_value": [10.0, -1.0, 0.0]})
    assert check_min_value(df, "freight_value", 0) == 1


def test_min_value_exclusive_flags_zero_price():
    df = pd.DataFrame({"price": [10.0, 0.0, 5.0]})
    assert check_min_value(df, "price", 0, exclusive=True) == 1


def test_min_value_exclusive_optional_ignores_nulls():
    df = pd.DataFrame({"product_weight_g": [100.0, None, 0.0]})
    # Only the present-but-invalid 0.0 should be flagged, not the NULL
    assert check_min_value_exclusive_optional(df, "product_weight_g", 0) == 1


def test_range_flags_out_of_bounds_review_score():
    df = pd.DataFrame({"review_score": [1, 5, 7, -1]})
    assert check_range(df, "review_score", 1, 5) == 2


def test_categorical_set_flags_invalid_state_code():
    df = pd.DataFrame({"customer_state": ["SP", "RJ", "ZZ"]})
    assert check_categorical_set(df, "customer_state", {"SP", "RJ"}) == 1


# --- referential integrity ----------------------------------------------

def test_referential_integrity_passes_when_all_children_have_parents():
    child = pd.DataFrame({"order_id": ["o1", "o2"]})
    parent = pd.DataFrame({"order_id": ["o1", "o2", "o3"]})
    assert check_referential_integrity(child, "order_id", parent, "order_id") == 0


def test_referential_integrity_flags_orphan_records():
    child = pd.DataFrame({"order_id": ["o1", "o99"]})
    parent = pd.DataFrame({"order_id": ["o1", "o2"]})
    assert check_referential_integrity(child, "order_id", parent, "order_id") == 1


# --- timeliness ------------------------------------------------------------

def test_date_order_passes_when_sequence_is_valid():
    df = pd.DataFrame({
        "order_purchase_timestamp": pd.to_datetime(["2024-01-01"]),
        "order_approved_at": pd.to_datetime(["2024-01-02"]),
    })
    assert check_date_order(df, "order_approved_at", "order_purchase_timestamp") == 0


def test_date_order_flags_impossible_sequence():
    df = pd.DataFrame({
        "order_purchase_timestamp": pd.to_datetime(["2024-01-05"]),
        "order_approved_at": pd.to_datetime(["2024-01-01"]),  # approved BEFORE purchase
    })
    assert check_date_order(df, "order_approved_at", "order_purchase_timestamp") == 1


def test_date_order_ignores_rows_with_missing_dates():
    df = pd.DataFrame({
        "order_purchase_timestamp": pd.to_datetime(["2024-01-05"]),
        "order_approved_at": pd.to_datetime([None]),
    })
    assert check_date_order(df, "order_approved_at", "order_purchase_timestamp") == 0


# --- conditional missingness (business-rule-aware completeness) ------------

def test_conditional_not_null_ignores_cancelled_orders():
    df = pd.DataFrame({
        "order_status": ["canceled", "delivered"],
        "order_delivered_customer_date": [None, None],
    })
    # only the 'delivered' row should be flagged
    assert check_conditional_not_null(df, "order_delivered_customer_date", "order_status", "delivered") == 1


def test_conditional_not_null_passes_when_delivered_orders_have_dates():
    df = pd.DataFrame({
        "order_status": ["delivered", "delivered"],
        "order_delivered_customer_date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
    })
    assert check_conditional_not_null(df, "order_delivered_customer_date", "order_status", "delivered") == 0
