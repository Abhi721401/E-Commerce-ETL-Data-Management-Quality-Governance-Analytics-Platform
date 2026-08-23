"""
dags/olist_etl_dag.py
----------------------
STEP 18 — Airflow orchestration for the Olist Data Management, Quality &
Governance Analytics Platform.

Pipeline:
    extract -> profile -> validate -> transform -> quality_score
             -> reconcile -> load_postgres -> generate_report

Design notes:
    - Each task is a thin PythonOperator wrapper around the corresponding
      src/*.py module so the SAME code runs identically whether invoked
      manually (`python -m src.reporting`) or orchestrated by Airflow.
    - XComs pass lightweight summaries between tasks (row counts, statuses)
      rather than full DataFrames, since large DataFrames should not be
      serialized through the metadata database. Each task independently
      re-reads what it needs from data/raw or data/processed via the
      src modules, which is the standard pattern for pandas-based Airflow
      ETL DAGs at this scale.
    - The DAG fails (raises AirflowFailException) when the reconciliation
      status is FAIL or there are open Critical-severity issues, so a
      genuine control failure stops the pipeline instead of silently
      producing a bad report.
    - Retries are configured for tasks touching external state (load to
      PostgreSQL) since transient connection issues are the most likely
      failure mode there.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.exceptions import AirflowFailException
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "data-governance-team",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def _extract(**context):
    from src.extract import extract_all
    data = extract_all()
    context["ti"].xcom_push(key="row_counts", value={k: len(v) for k, v in data.items()})


def _profile(**context):
    from src.extract import extract_all
    from src.profile import profile_all
    data = extract_all()
    report = profile_all(data)
    context["ti"].xcom_push(key="total_rows", value=report["summary"]["total_rows_all_datasets"])


def _validate(**context):
    from src.extract import extract_all
    from src.reporting import write_issue_register
    from src.validation import run_validation
    data = extract_all()
    issues = run_validation(data)
    write_issue_register(issues)
    critical_open = sum(1 for i in issues if i["severity"] == "Critical" and i["status"] == "Open")
    context["ti"].xcom_push(key="critical_open_issues", value=critical_open)


def _transform(**context):
    from src.extract import extract_all
    from src.transform import run_transformation
    data = extract_all()
    processed = run_transformation(data)
    context["ti"].xcom_push(key="processed_row_counts", value={k: len(v) for k, v in processed.items()})


def _quality_score(**context):
    from src.extract import extract_all
    from src.quality_score import compute_quality_score
    from src.validation import run_validation
    data = extract_all()
    issues = run_validation(data)
    counts = {name: len(df) for name, df in data.items()}
    scorecard = compute_quality_score(issues, counts)
    context["ti"].xcom_push(key="overall_score_pct", value=scorecard.get("overall_score_pct"))


def _reconcile(**context):
    from src.extract import extract_all
    from src.reconciliation import run_reconciliation
    from src.transform import run_transformation
    raw = extract_all()
    processed = run_transformation(raw)
    report = run_reconciliation(raw, processed)
    context["ti"].xcom_push(key="reconciliation_status", value=report["overall_status"])
    if report["overall_status"] == "FAIL":
        raise AirflowFailException(
            f"Reconciliation FAILED: {report['checks_failed']} check(s) exceeded the "
            f"variance threshold. See reports/reconciliation_report.json."
        )


def _load_postgres(**context):
    from src.extract import extract_all
    from src.load import run_load
    from src.transform import run_transformation
    raw = extract_all()
    processed = run_transformation(raw)
    loaded_counts = run_load(processed)
    context["ti"].xcom_push(key="loaded_counts", value=loaded_counts)


def _generate_report(**context):
    from src.reporting import run_full_pipeline
    report = run_full_pipeline()
    if report["pipeline_status"] == "FAILED":
        raise AirflowFailException(
            "Pipeline completed with a FAILED status — critical open issues "
            "or a reconciliation failure were detected. See "
            "reports/pipeline_run_report.json for details."
        )


with DAG(
    dag_id="olist_etl_governance_pipeline",
    description="Extract, profile, validate, transform, score, reconcile, "
                 "load, and report on Olist e-commerce data quality & governance.",
    default_args=default_args,
    schedule_interval="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["olist", "data-governance", "data-quality", "etl"],
) as dag:

    extract_task = PythonOperator(task_id="extract", python_callable=_extract)
    profile_task = PythonOperator(task_id="profile", python_callable=_profile)
    validate_task = PythonOperator(task_id="validate", python_callable=_validate)
    transform_task = PythonOperator(task_id="transform", python_callable=_transform)
    quality_score_task = PythonOperator(task_id="quality_score", python_callable=_quality_score)
    reconcile_task = PythonOperator(task_id="reconcile", python_callable=_reconcile)
    load_task = PythonOperator(
        task_id="load_postgres",
        python_callable=_load_postgres,
        retries=3,
        retry_delay=timedelta(minutes=2),
    )
    report_task = PythonOperator(task_id="generate_report", python_callable=_generate_report)

    extract_task >> profile_task >> validate_task >> transform_task
    transform_task >> quality_score_task >> reconcile_task >> load_task >> report_task
