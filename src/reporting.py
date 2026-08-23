"""
reporting.py
------------
AUTOMATED REPORTING layer (STEP 16).

Purpose:
    Produce a single consolidated pipeline_run_report.json (and printed
    summary) each time the pipeline executes, containing:
      - run timestamp
      - records processed per dataset
      - validation results summary
      - quality scores
      - issue summary (by severity / status)
      - reconciliation results
      - any major/critical failures

Connects to:
    - Consumes outputs from profile.py, validation.py, quality_score.py,
      reconciliation.py.
    - Written to reports/pipeline_run_report.json, which is also the file
      the Airflow DAG's final task reads to decide whether to raise an
      alert (e.g. on 'FAIL' reconciliation status or Critical open issues).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from src.config import ISSUE_REGISTER_PATH, PIPELINE_RUN_REPORT_PATH
from src.logging_setup import get_logger

logger = get_logger(__name__)


def write_issue_register(issues: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(issues)
    ISSUE_REGISTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ISSUE_REGISTER_PATH, index=False)
    logger.info("Issue register written to %s (%d records)", ISSUE_REGISTER_PATH, len(df))
    return df


def generate_pipeline_report(
    profile_report: dict[str, Any],
    issues: list[dict[str, Any]],
    quality_scorecard: dict[str, Any],
    reconciliation_report: dict[str, Any],
) -> dict[str, Any]:
    issues_df = pd.DataFrame(issues)

    open_issues = issues_df[issues_df["status"] == "Open"] if not issues_df.empty else pd.DataFrame()
    critical_open = open_issues[open_issues["severity"] == "Critical"] if not open_issues.empty else pd.DataFrame()

    issue_summary = {
        "total_rules_evaluated": int(len(issues_df)),
        "open_issues": int(len(open_issues)),
        "resolved_issues": int((issues_df["status"] == "Resolved").sum()) if not issues_df.empty else 0,
        "critical_open_issues": int(len(critical_open)),
        "issues_by_severity": (
            issues_df[issues_df["status"] == "Open"]["severity"].value_counts().to_dict()
            if not issues_df.empty else {}
        ),
        "issues_by_dataset": (
            issues_df[issues_df["status"] == "Open"]["dataset"].value_counts().to_dict()
            if not issues_df.empty else {}
        ),
    }

    report = {
        "pipeline_run_timestamp": datetime.now(timezone.utc).isoformat(),
        "records_processed": {
            name: d["row_count"] for name, d in profile_report.get("datasets", {}).items()
        },
        "total_records_processed": profile_report.get("summary", {}).get("total_rows_all_datasets"),
        "validation_summary": issue_summary,
        "quality_scorecard": {
            "overall_score_pct": quality_scorecard.get("overall_score_pct"),
            "overall_dimension_scores_pct": quality_scorecard.get("overall_dimension_scores_pct"),
        },
        "reconciliation_summary": {
            "overall_status": reconciliation_report.get("overall_status"),
            "checks_total": reconciliation_report.get("checks_total"),
            "checks_passed": reconciliation_report.get("checks_passed"),
            "checks_warning": reconciliation_report.get("checks_warning"),
            "checks_failed": reconciliation_report.get("checks_failed"),
        },
        "pipeline_status": (
            "FAILED" if reconciliation_report.get("overall_status") == "FAIL" or issue_summary["critical_open_issues"] > 0
            else "PASSED_WITH_WARNINGS" if reconciliation_report.get("overall_status") == "WARNING"
            else "PASSED"
        ),
    }

    PIPELINE_RUN_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PIPELINE_RUN_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info(
        "Pipeline run report written to %s — status: %s",
        PIPELINE_RUN_REPORT_PATH, report["pipeline_status"],
    )
    return report


def run_full_pipeline() -> dict[str, Any]:
    """Convenience entry point that runs every stage end-to-end and returns the final report."""
    from src.extract import extract_all
    from src.profile import profile_all
    from src.quality_score import compute_quality_score
    from src.reconciliation import run_reconciliation
    from src.transform import run_transformation
    from src.validation import run_validation

    logger.info("=== Pipeline run starting ===")
    raw = extract_all()
    profile_report = profile_all(raw)
    issues = run_validation(raw)
    write_issue_register(issues)

    row_counts = {name: len(df) for name, df in raw.items()}
    scorecard = compute_quality_score(issues, row_counts)

    processed = run_transformation(raw)
    reconciliation_report = run_reconciliation(raw, processed)

    final_report = generate_pipeline_report(profile_report, issues, scorecard, reconciliation_report)
    logger.info("=== Pipeline run complete: %s ===", final_report["pipeline_status"])
    return final_report


if __name__ == "__main__":
    result = run_full_pipeline()
    print(json.dumps(result, indent=2, default=str))
