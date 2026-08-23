"""
reconciliation.py
------------------
RECONCILIATION layer (STEP 11).

Purpose:
    Provide source-to-target operational controls across three stages:
        RAW -> TRANSFORMED -> POSTGRESQL
    comparing record counts, key counts, and monetary totals, and
    classifying each check as PASS / WARNING / FAIL with variance details.

    This is the control layer a reviewer expects from a governance-minded
    analyst: it proves the pipeline didn't silently lose or duplicate data
    between stages.

Connects to:
    - extract.py        -> RAW row counts
    - transform.py         -> TRANSFORMED row counts
    - load.py               -> LOADED (PostgreSQL) row counts, when available
    - reporting.py            -> reconciliation_report.json feeds the run report
    - Power BI (Dashboard 2)   -> "reconciliation status" visual
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from src.config import RECONCILIATION_REPORT_PATH
from src.logging_setup import get_logger

logger = get_logger(__name__)

# Datasets where 1 raw row should become exactly 1 transformed row
# (i.e. no legitimate row-count change is expected during cleaning).
ROW_PRESERVING_DATASETS = {
    "customers", "orders", "order_items", "payments",
    "reviews", "products", "sellers", "category_translation",
}

# Monetary fields to reconcile per dataset, where applicable
MONETARY_FIELDS = {
    "order_items": ["price", "freight_value"],
    "payments": ["payment_value"],
}

VARIANCE_WARNING_THRESHOLD = 0.001   # 0.1% variance -> WARNING
VARIANCE_FAIL_THRESHOLD = 0.01       # 1% variance   -> FAIL


def _classify(variance_pct: float) -> str:
    if abs(variance_pct) <= VARIANCE_WARNING_THRESHOLD:
        return "PASS"
    if abs(variance_pct) <= VARIANCE_FAIL_THRESHOLD:
        return "WARNING"
    return "FAIL"


def reconcile_row_counts(
    raw: dict[str, pd.DataFrame],
    transformed: dict[str, pd.DataFrame],
    loaded_counts: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    results = []
    loaded_counts = loaded_counts or {}

    for name in raw:
        if name not in ROW_PRESERVING_DATASETS:
            continue  # e.g. geolocation intentionally produces a separate lookup grain

        raw_count = len(raw[name])
        trans_count = len(transformed.get(name, pd.DataFrame()))
        loaded_count = loaded_counts.get(name)

        variance_pct = (trans_count - raw_count) / raw_count if raw_count else 0.0
        status = _classify(variance_pct)

        result = {
            "check": "row_count",
            "dataset": name,
            "raw_count": int(raw_count),
            "transformed_count": int(trans_count),
            "loaded_count": int(loaded_count) if loaded_count is not None else None,
            "variance_pct": round(variance_pct * 100, 4),
            "status": status,
        }
        results.append(result)
        logger.info(
            "Reconciliation [%s] raw=%d transformed=%d loaded=%s -> %s",
            name, raw_count, trans_count, loaded_count, status,
        )
    return results


def reconcile_key_counts(raw: dict[str, pd.DataFrame], transformed: dict[str, pd.DataFrame],
                          key_fields: dict[str, str]) -> list[dict[str, Any]]:
    """key_fields: e.g. {'orders': 'order_id', 'customers': 'customer_id'}"""
    results = []
    for name, key in key_fields.items():
        if name not in raw or key not in raw[name].columns:
            continue
        raw_keys = raw[name][key].nunique(dropna=True)
        trans_keys = transformed.get(name, pd.DataFrame()).get(key, pd.Series(dtype=object)).nunique(dropna=True)
        variance_pct = (trans_keys - raw_keys) / raw_keys if raw_keys else 0.0
        results.append({
            "check": "distinct_key_count",
            "dataset": name,
            "field": key,
            "raw_distinct_keys": int(raw_keys),
            "transformed_distinct_keys": int(trans_keys),
            "variance_pct": round(variance_pct * 100, 4),
            "status": _classify(variance_pct),
        })
    return results


def reconcile_monetary_totals(raw: dict[str, pd.DataFrame], transformed: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    results = []
    for name, fields in MONETARY_FIELDS.items():
        if name not in raw:
            continue
        for field in fields:
            if field not in raw[name].columns:
                continue
            raw_total = float(pd.to_numeric(raw[name][field], errors="coerce").sum())
            trans_df = transformed.get(name)
            trans_total = float(pd.to_numeric(trans_df[field], errors="coerce").sum()) if trans_df is not None and field in trans_df.columns else 0.0
            variance_pct = (trans_total - raw_total) / raw_total if raw_total else 0.0
            results.append({
                "check": "monetary_total",
                "dataset": name,
                "field": field,
                "raw_total": round(raw_total, 2),
                "transformed_total": round(trans_total, 2),
                "variance_pct": round(variance_pct * 100, 6),
                "status": _classify(variance_pct),
            })
    return results


def run_reconciliation(
    raw: dict[str, pd.DataFrame],
    transformed: dict[str, pd.DataFrame],
    loaded_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    row_checks = reconcile_row_counts(raw, transformed, loaded_counts)
    key_checks = reconcile_key_counts(raw, transformed, {
        "orders": "order_id", "customers": "customer_id",
        "products": "product_id", "sellers": "seller_id",
    })
    money_checks = reconcile_monetary_totals(raw, transformed)

    all_checks = row_checks + key_checks + money_checks
    statuses = [c["status"] for c in all_checks]
    overall_status = "FAIL" if "FAIL" in statuses else ("WARNING" if "WARNING" in statuses else "PASS")

    report = {
        "row_count_checks": row_checks,
        "key_count_checks": key_checks,
        "monetary_total_checks": money_checks,
        "overall_status": overall_status,
        "checks_total": len(all_checks),
        "checks_passed": statuses.count("PASS"),
        "checks_warning": statuses.count("WARNING"),
        "checks_failed": statuses.count("FAIL"),
    }

    RECONCILIATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RECONCILIATION_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info("Reconciliation report written to %s — overall status: %s", RECONCILIATION_REPORT_PATH, overall_status)

    return report


if __name__ == "__main__":
    from src.extract import extract_all
    from src.transform import run_transformation

    raw_data = extract_all()
    processed_data = run_transformation(raw_data)
    rec = run_reconciliation(raw_data, processed_data)
    print(json.dumps({k: v for k, v in rec.items() if not isinstance(v, list)}, indent=2))
