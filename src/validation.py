"""
validation.py
--------------
DATA VALIDATION layer implementing six quality dimensions:
    1. Completeness            4. Consistency
    2. Uniqueness               5. Referential Integrity
    3. Validity                 6. Timeliness

Design principle (per project addendum):
    Rules are NOT hardcoded per-dataset. The engine reads
    governance/quality_rules.csv and dispatches to a small library of
    generic validator functions based on `validation_type`. This means
    adding/adjusting a rule is a config change, not a code change.

    Business-aware exceptions (Olist-specific judgment calls) are still
    respected:
      - review_comment_title / review_comment_message are optional -> NOT
        validated as "not_null" (no rule exists for them).
      - order_delivered_customer_date is only flagged missing when
        order_status == 'delivered' (conditional_not_null), not for
        cancelled/unavailable/etc. orders.
      - product physical attributes are validated as "optional but must be
        positive when present", never assumed to be 0.

Connects to:
    - extract.py        -> raw datasets are the input
    - config.py            -> QUALITY_RULES_PATH, severity/category constants
    - quality_score.py      -> consumes the issue list this module produces
    - reconciliation.py      -> reuses referential_integrity helper
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from src.config import (
    QUALITY_RULES_PATH,
    VALID_BRAZIL_STATES,
    VALID_ORDER_STATUSES,
)
from src.logging_setup import get_logger

logger = get_logger(__name__)

_NAMED_SETS = {
    "VALID_BRAZIL_STATES": VALID_BRAZIL_STATES,
    "VALID_ORDER_STATUSES": VALID_ORDER_STATUSES,
}


def load_quality_rules(path=QUALITY_RULES_PATH) -> pd.DataFrame:
    rules = pd.read_csv(path)
    rules["active"] = rules["active"].astype(str).str.upper().eq("TRUE")
    return rules[rules["active"]].copy()


def _new_issue(
    rule_id: str,
    dataset: str,
    field: str,
    description: str,
    severity: str,
    affected_records: int,
) -> dict[str, Any]:
    return {
        "issue_id": f"ISS-{uuid.uuid4().hex[:10].upper()}",
        "rule_id": rule_id,
        "dataset": dataset,
        "field": field,
        "issue_description": description,
        "severity": severity,
        "affected_records": int(affected_records),
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "status": "Open" if affected_records > 0 else "Resolved",
        "resolution": "" if affected_records > 0 else "No violations found at validation time.",
        "resolved_at": "" if affected_records > 0 else datetime.now(timezone.utc).isoformat(),
    }


# --------------------------------------------------------------------------
# Individual dimension validators — each returns (affected_count, details)
# --------------------------------------------------------------------------

def check_not_null(df: pd.DataFrame, field: str) -> int:
    if field not in df.columns:
        return 0
    return int(df[field].isnull().sum())


def check_unique(df: pd.DataFrame, field: str) -> int:
    if field not in df.columns:
        return 0
    non_null = df[field].dropna()
    return int(non_null.duplicated(keep=False).sum())


def check_composite_unique(df: pd.DataFrame, field: str, field2: str) -> int:
    if field not in df.columns or field2 not in df.columns:
        return 0
    subset = df[[field, field2]].dropna()
    return int(subset.duplicated(keep=False).sum())


def check_min_value(df: pd.DataFrame, field: str, threshold: float, exclusive: bool = False) -> int:
    if field not in df.columns:
        return 0
    series = pd.to_numeric(df[field], errors="coerce")
    if exclusive:
        return int((series <= threshold).sum())
    return int((series < threshold).sum())


def check_min_value_exclusive_optional(df: pd.DataFrame, field: str, threshold: float) -> int:
    """Only flags rows where the value IS present but invalid (<=threshold)."""
    if field not in df.columns:
        return 0
    series = pd.to_numeric(df[field], errors="coerce")
    present = df[field].notnull()
    return int(((series <= threshold) & present).sum())


def check_range(df: pd.DataFrame, field: str, low: float, high: float) -> int:
    if field not in df.columns:
        return 0
    series = pd.to_numeric(df[field], errors="coerce")
    return int((~series.between(low, high)).sum())


def check_categorical_set(df: pd.DataFrame, field: str, valid_set: set) -> int:
    if field not in df.columns:
        return 0
    non_null = df[field].dropna()
    return int((~non_null.isin(valid_set)).sum())


def check_referential_integrity(child_df: pd.DataFrame, child_field: str,
                                 parent_df: pd.DataFrame, parent_field: str) -> int:
    if child_field not in child_df.columns or parent_field not in parent_df.columns:
        return 0
    parent_keys = set(parent_df[parent_field].dropna().unique())
    child_values = child_df[child_field].dropna()
    return int((~child_values.isin(parent_keys)).sum())


def check_date_order(df: pd.DataFrame, later_field: str, earlier_field: str) -> int:
    """Flags rows where later_field < earlier_field, only when BOTH are present."""
    if later_field not in df.columns or earlier_field not in df.columns:
        return 0
    later = pd.to_datetime(df[later_field], errors="coerce")
    earlier = pd.to_datetime(df[earlier_field], errors="coerce")
    both_present = later.notnull() & earlier.notnull()
    violation = both_present & (later < earlier)
    return int(violation.sum())


def check_conditional_not_null(df: pd.DataFrame, field: str, condition_field: str,
                                condition_value: str) -> int:
    """Flags null `field` only for rows where condition_field == condition_value."""
    if field not in df.columns or condition_field not in df.columns:
        return 0
    relevant = df[condition_field].astype(str).str.lower() == condition_value.lower()
    return int((relevant & df[field].isnull()).sum())


# --------------------------------------------------------------------------
# Rule dispatch engine
# --------------------------------------------------------------------------

def _resolve_param_set(param: str) -> set:
    if param in _NAMED_SETS:
        return _NAMED_SETS[param]
    return set(str(param).split(","))


def run_validation(datasets: dict[str, pd.DataFrame], rules_path=QUALITY_RULES_PATH) -> list[dict[str, Any]]:
    """
    Execute every active rule from quality_rules.csv against the supplied
    datasets and return a list of issue-register records (one per rule,
    including rules with 0 affected records so passing checks are visible).
    """
    rules = load_quality_rules(rules_path)
    issues: list[dict[str, Any]] = []

    for _, rule in rules.iterrows():
        rule_id = rule["rule_id"]
        dataset_name = rule["dataset"]
        field = rule["field"]
        vtype = rule["validation_type"]
        params = "" if pd.isna(rule.get("params")) else str(rule.get("params"))
        severity = rule["severity"]
        description = rule["rule_description"]

        if dataset_name not in datasets:
            logger.warning("Rule %s references missing dataset '%s' — skipped.", rule_id, dataset_name)
            continue
        df = datasets[dataset_name]
        affected = 0

        try:
            if vtype == "not_null":
                affected = check_not_null(df, field)
            elif vtype == "unique":
                affected = check_unique(df, field)
            elif vtype == "composite_unique":
                affected = check_composite_unique(df, field, params)
            elif vtype == "min_value":
                affected = check_min_value(df, field, float(params))
            elif vtype == "min_value_exclusive":
                affected = check_min_value(df, field, float(params), exclusive=True)
            elif vtype == "min_value_exclusive_optional":
                affected = check_min_value_exclusive_optional(df, field, float(params))
            elif vtype == "range":
                low, high = (float(x) for x in params.split(";"))
                affected = check_range(df, field, low, high)
            elif vtype == "categorical_set":
                affected = check_categorical_set(df, field, _resolve_param_set(params))
            elif vtype == "referential_integrity":
                parent_name, parent_field = params.split(":")
                if parent_name not in datasets:
                    logger.warning("Rule %s references missing parent dataset '%s'.", rule_id, parent_name)
                    continue
                affected = check_referential_integrity(df, field, datasets[parent_name], parent_field)
            elif vtype == "date_order":
                affected = check_date_order(df, field, params)
            elif vtype == "conditional_not_null":
                cond_field, cond_value = params.split(":")
                affected = check_conditional_not_null(df, field, cond_field, cond_value)
            else:
                logger.warning("Unknown validation_type '%s' for rule %s — skipped.", vtype, rule_id)
                continue
        except Exception as exc:  # keep the pipeline resilient to a single bad rule
            logger.error("Rule %s failed to execute: %s", rule_id, exc)
            continue

        issues.append(_new_issue(rule_id, dataset_name, field, description, severity, affected))

    total_flagged = sum(i["affected_records"] for i in issues)
    logger.info(
        "Validation complete: %d rules evaluated, %d total affected records across all rules.",
        len(issues), total_flagged,
    )
    return issues


if __name__ == "__main__":
    from src.extract import extract_all

    data = extract_all()
    result = run_validation(data)
    for r in result:
        flag = "⚠" if r["affected_records"] > 0 else "✓"
        print(f"{flag} {r['rule_id']:<8} {r['dataset']:<12} {r['field']:<25} affected={r['affected_records']}")
