"""
quality_score.py
-----------------
DATA QUALITY SCORE layer (STEP 10).

Purpose:
    Convert the raw issue list produced by validation.py into a documented,
    weighted quality scorecard across the six quality dimensions, per
    dataset, and overall.

Scoring methodology (documented, not fabricated):
    For each rule, we compute a pass rate:
        pass_rate = 1 - (affected_records / rows_evaluated)
    where rows_evaluated is the row count of the rule's dataset at
    validation time (or, for referential_integrity / composite rules, the
    row count of the child dataset — i.e. the population the rule actually
    checks).

    dimension_score(dataset) = mean of pass_rate across all rules for that
                                 dataset within that dimension
    dataset_score              = weighted mean of that dataset's dimension
                                 scores, using QUALITY_DIMENSION_WEIGHTS
    overall_score               = row-count-weighted mean of dataset_scores
                                 across all datasets (larger datasets carry
                                 proportionally more weight)

    Weights (STEP 10 / QUALITY_DIMENSION_WEIGHTS in config.py):
        completeness            20%
        uniqueness               20%
        validity                  20%
        consistency               15%
        referential_integrity      15%
        timeliness                 10%

Connects to:
    - validation.py    -> supplies the list of issue dicts this module scores
    - profile.py         -> row counts used as the scoring denominator
    - reporting.py        -> quality_scorecard.json feeds the run report
    - Power BI (Dashboard 2) -> quality_scorecard.json / SQL view is the
      direct source for "quality score by dataset" and "quality score by
      dimension" visuals
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from src.config import QUALITY_DIMENSION_WEIGHTS, QUALITY_RULES_PATH, QUALITY_SCORECARD_PATH
from src.logging_setup import get_logger

logger = get_logger(__name__)


def _pass_rate(row_count: int, affected: int) -> float:
    if row_count <= 0:
        return 1.0
    rate = 1 - (affected / row_count)
    return max(0.0, min(1.0, rate))


def compute_quality_score(
    issues: list[dict[str, Any]],
    row_counts: dict[str, int],
    rules_path=QUALITY_RULES_PATH,
) -> dict[str, Any]:
    rules = pd.read_csv(rules_path)
    rules_by_id = rules.set_index("rule_id").to_dict(orient="index")

    issues_df = pd.DataFrame(issues)
    if issues_df.empty:
        logger.warning("No issues supplied to quality_score — returning empty scorecard.")
        return {"dataset_scores": {}, "dimension_scores": {}, "overall_score": None}

    issues_df["dimension"] = issues_df["rule_id"].map(lambda r: rules_by_id.get(r, {}).get("dimension"))
    issues_df["row_count"] = issues_df["dataset"].map(lambda d: row_counts.get(d, 0))
    issues_df["pass_rate"] = issues_df.apply(
        lambda r: _pass_rate(r["row_count"], r["affected_records"]), axis=1
    )

    # dimension score per dataset
    dim_scores = (
        issues_df.groupby(["dataset", "dimension"])["pass_rate"].mean().reset_index()
    )

    dataset_scores: dict[str, Any] = {}
    for dataset in dim_scores["dataset"].unique():
        sub = dim_scores[dim_scores["dataset"] == dataset]
        dims = dict(zip(sub["dimension"], sub["pass_rate"]))
        weighted_sum = 0.0
        weight_total = 0.0
        for dim, weight in QUALITY_DIMENSION_WEIGHTS.items():
            if dim in dims:
                weighted_sum += dims[dim] * weight
                weight_total += weight
        dataset_score = (weighted_sum / weight_total) if weight_total > 0 else None
        dataset_scores[dataset] = {
            "dimension_scores_pct": {k: round(v * 100, 2) for k, v in dims.items()},
            "dataset_score_pct": round(dataset_score * 100, 2) if dataset_score is not None else None,
            "row_count": row_counts.get(dataset, 0),
        }

    # overall dimension scores across all datasets (row-count weighted)
    overall_dimension_scores: dict[str, float] = {}
    for dim in QUALITY_DIMENSION_WEIGHTS:
        rows = []
        for dataset, info in dataset_scores.items():
            if dim in info["dimension_scores_pct"]:
                rows.append((info["row_count"], info["dimension_scores_pct"][dim]))
        if rows:
            total_rows = sum(r for r, _ in rows) or 1
            overall_dimension_scores[dim] = round(
                sum(r * s for r, s in rows) / total_rows, 2
            )

    # overall score = row-count-weighted mean of dataset scores
    scored = [(v["row_count"], v["dataset_score_pct"]) for v in dataset_scores.values() if v["dataset_score_pct"] is not None]
    total_rows = sum(r for r, _ in scored) or 1
    overall_score = round(sum(r * s for r, s in scored) / total_rows, 2) if scored else None

    scorecard = {
        "methodology": {
            "dimension_weights": QUALITY_DIMENSION_WEIGHTS,
            "dataset_score_formula": "weighted mean of dimension pass-rates using QUALITY_DIMENSION_WEIGHTS",
            "overall_score_formula": "row-count-weighted mean of dataset scores",
        },
        "dataset_scores": dataset_scores,
        "overall_dimension_scores_pct": overall_dimension_scores,
        "overall_score_pct": overall_score,
    }

    QUALITY_SCORECARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(QUALITY_SCORECARD_PATH, "w", encoding="utf-8") as f:
        json.dump(scorecard, f, indent=2, default=str)
    logger.info("Quality scorecard written to %s — overall score: %s%%", QUALITY_SCORECARD_PATH, overall_score)

    return scorecard


if __name__ == "__main__":
    from src.extract import extract_all
    from src.validation import run_validation

    data = extract_all()
    issue_list = run_validation(data)
    counts = {name: len(df) for name, df in data.items()}
    card = compute_quality_score(issue_list, counts)
    print(json.dumps(card["overall_dimension_scores_pct"], indent=2))
    print("Overall score:", card["overall_score_pct"])
