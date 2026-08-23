"""
test_reconciliation.py
-----------------------
Unit tests for src/reconciliation.py covering:
    - row-count preservation checks (PASS)
    - row-count variance beyond threshold (FAIL)
    - key-count reconciliation
    - monetary total reconciliation
"""

import pandas as pd

from src.reconciliation import (
    reconcile_key_counts,
    reconcile_monetary_totals,
    reconcile_row_counts,
    run_reconciliation,
)


def _sample_raw_and_transformed(orders_transformed_n=100, items_price_delta=0.0):
    raw = {
        "orders": pd.DataFrame({"order_id": [f"o{i}" for i in range(100)]}),
        "order_items": pd.DataFrame({
            "order_id": [f"o{i}" for i in range(100)],
            "price": [10.0] * 100,
            "freight_value": [1.0] * 100,
        }),
        "customers": pd.DataFrame({"customer_id": [f"c{i}" for i in range(100)]}),
        "payments": pd.DataFrame({"order_id": [f"o{i}" for i in range(100)], "payment_value": [11.0] * 100}),
        "reviews": pd.DataFrame({"order_id": [f"o{i}" for i in range(100)]}),
        "products": pd.DataFrame({"product_id": [f"p{i}" for i in range(100)]}),
        "sellers": pd.DataFrame({"seller_id": [f"s{i}" for i in range(100)]}),
        "category_translation": pd.DataFrame({"product_category_name": [f"cat{i}" for i in range(100)]}),
    }
    transformed = {k: v.copy() for k, v in raw.items()}
    transformed["orders"] = transformed["orders"].iloc[:orders_transformed_n].copy()
    transformed["order_items"]["price"] = transformed["order_items"]["price"] + items_price_delta
    return raw, transformed


def test_row_counts_pass_when_preserved():
    raw, transformed = _sample_raw_and_transformed(orders_transformed_n=100)
    results = reconcile_row_counts(raw, transformed)
    orders_result = next(r for r in results if r["dataset"] == "orders")
    assert orders_result["status"] == "PASS"
    assert orders_result["raw_count"] == orders_result["transformed_count"] == 100


def test_row_counts_fail_on_large_variance():
    raw, transformed = _sample_raw_and_transformed(orders_transformed_n=50)  # 50% row loss
    results = reconcile_row_counts(raw, transformed)
    orders_result = next(r for r in results if r["dataset"] == "orders")
    assert orders_result["status"] == "FAIL"


def test_key_count_reconciliation_matches_when_no_dedup():
    raw, transformed = _sample_raw_and_transformed()
    results = reconcile_key_counts(raw, transformed, {"orders": "order_id"})
    assert results[0]["status"] == "PASS"
    assert results[0]["raw_distinct_keys"] == results[0]["transformed_distinct_keys"]


def test_monetary_totals_flag_variance():
    raw, transformed = _sample_raw_and_transformed(items_price_delta=5.0)  # inflate every price by 5
    results = reconcile_monetary_totals(raw, transformed)
    price_check = next(r for r in results if r["dataset"] == "order_items" and r["field"] == "price")
    assert price_check["status"] == "FAIL"
    assert price_check["transformed_total"] > price_check["raw_total"]


def test_monetary_totals_pass_when_preserved():
    raw, transformed = _sample_raw_and_transformed(items_price_delta=0.0)
    results = reconcile_monetary_totals(raw, transformed)
    price_check = next(r for r in results if r["dataset"] == "order_items" and r["field"] == "price")
    assert price_check["status"] == "PASS"


def test_run_reconciliation_overall_status_reflects_worst_check(tmp_path, monkeypatch):
    import src.reconciliation as recon_module
    monkeypatch.setattr(recon_module, "RECONCILIATION_REPORT_PATH", tmp_path / "reconciliation_report.json")

    raw, transformed = _sample_raw_and_transformed(orders_transformed_n=50)
    report = run_reconciliation(raw, transformed)
    assert report["overall_status"] == "FAIL"
    assert report["checks_failed"] >= 1
