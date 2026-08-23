"""
profile.py
----------
DATA PROFILING layer.

Purpose:
    For every raw dataset, calculate schema, missingness, duplication, and
    candidate-key statistics DIRECTLY from the data (never hardcoded). This
    answers: how many records were received, which fields are missing,
    which fields contain duplicates, and which columns need transformation.

Connects to:
    - extract.py       -> receives the dict of raw DataFrames
    - validation.py     -> quality rules build on profiling findings
    - reporting.py       -> profile_report.json feeds the pipeline run report
    - config.py           -> PROFILE_REPORT_PATH
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from src.config import PROFILE_REPORT_PATH
from src.logging_setup import get_logger

logger = get_logger(__name__)


def _candidate_keys(df: pd.DataFrame, max_cols_to_check: int = 6) -> list[str]:
    """
    Identify single columns that are fully unique and non-null — i.e.
    plausible primary-key candidates. Only checks columns that look like
    identifiers (name contains '_id' or 'id') to keep this fast and relevant.
    """
    candidates = []
    id_like_cols = [c for c in df.columns if "id" in c.lower()][:max_cols_to_check]
    for col in id_like_cols:
        series = df[col]
        if series.isnull().sum() == 0 and series.is_unique:
            candidates.append(col)
    return candidates


def profile_dataset(name: str, df: pd.DataFrame) -> dict[str, Any]:
    """Compute a full profile for a single dataset."""
    n_rows, n_cols = df.shape
    missing_count = int(df.isnull().sum().sum())
    missing_by_col = df.isnull().sum()
    missing_pct_by_col = (missing_by_col / n_rows * 100).round(3) if n_rows else missing_by_col

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    numeric_stats = df[numeric_cols].describe().to_dict() if numeric_cols else {}

    profile = {
        "dataset": name,
        "row_count": int(n_rows),
        "column_count": int(n_cols),
        "columns": list(df.columns),
        "dtypes": {c: str(t) for c, t in df.dtypes.items()},
        "missing_cells_total": missing_count,
        "missing_by_column": {c: int(v) for c, v in missing_by_col.items() if v > 0},
        "missing_pct_by_column": {c: float(v) for c, v in missing_pct_by_col.items() if v > 0},
        "duplicate_full_rows": int(df.duplicated().sum()),
        "unique_counts_by_column": {c: int(df[c].nunique(dropna=True)) for c in df.columns},
        "primary_key_candidates": _candidate_keys(df),
        "numeric_summary": numeric_stats,
    }
    logger.info(
        "Profiled '%s': %d rows, %d cols, %d missing cells, %d duplicate rows.",
        name, n_rows, n_cols, missing_count, profile["duplicate_full_rows"],
    )
    return profile


def profile_all(datasets: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Profile every dataset in the supplied dict and write a JSON report."""
    report: dict[str, Any] = {"datasets": {}}
    for name, df in datasets.items():
        report["datasets"][name] = profile_dataset(name, df)

    report["summary"] = {
        "total_datasets_profiled": len(datasets),
        "total_rows_all_datasets": sum(d["row_count"] for d in report["datasets"].values()),
        "total_missing_cells_all_datasets": sum(
            d["missing_cells_total"] for d in report["datasets"].values()
        ),
        "total_duplicate_rows_all_datasets": sum(
            d["duplicate_full_rows"] for d in report["datasets"].values()
        ),
    }

    PROFILE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PROFILE_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info("Profile report written to %s", PROFILE_REPORT_PATH)

    return report


if __name__ == "__main__":
    from src.extract import extract_all

    data = extract_all()
    result = profile_all(data)
    print(json.dumps(result["summary"], indent=2))
