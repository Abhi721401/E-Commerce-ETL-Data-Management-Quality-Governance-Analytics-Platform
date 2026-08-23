"""
config.py
---------
Central configuration for the Olist Data Management, Quality & Governance
Analytics Platform.

Purpose:
    Every other module imports paths, filenames, and thresholds from here
    instead of hardcoding them. This keeps the pipeline configurable and
    makes it trivial to point the project at a different environment
    (local dev, Docker, CI) by only changing environment variables.

Connects to:
    Imported by extract.py, profile.py, validation.py, transform.py,
    quality_score.py, reconciliation.py, load.py, reporting.py, and the
    Airflow DAG.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a .env file if present (never committed to git)
load_dotenv()

# --------------------------------------------------------------------------
# Project root & directory layout
# --------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]

DATA_DIR: Path = PROJECT_ROOT / "data"
RAW_DATA_DIR: Path = DATA_DIR / "raw"
PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"

GOVERNANCE_DIR: Path = PROJECT_ROOT / "governance"
REPORTS_DIR: Path = PROJECT_ROOT / "reports"
EXCEL_DIR: Path = PROJECT_ROOT / "excel"
SQL_DIR: Path = PROJECT_ROOT / "sql"

for _dir in (PROCESSED_DATA_DIR, REPORTS_DIR, EXCEL_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Raw source files (Olist Brazilian E-Commerce Public Dataset)
# --------------------------------------------------------------------------
RAW_FILES: dict[str, str] = {
    "customers": "olist_customers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

# --------------------------------------------------------------------------
# Processed (post-transformation) output files
# --------------------------------------------------------------------------
PROCESSED_FILES: dict[str, str] = {
    "customers": "customers_clean.parquet",
    "geolocation": "geolocation_clean.parquet",
    "geolocation_lookup": "geolocation_lookup.parquet",
    "order_items": "order_items_clean.parquet",
    "payments": "payments_clean.parquet",
    "reviews": "reviews_clean.parquet",
    "orders": "orders_clean.parquet",
    "products": "products_clean.parquet",
    "sellers": "sellers_clean.parquet",
    "category_translation": "category_translation_clean.parquet",
    "fact_sales": "fact_sales.parquet",
}

# --------------------------------------------------------------------------
# Governance reference files
# --------------------------------------------------------------------------
DATA_DICTIONARY_PATH: Path = GOVERNANCE_DIR / "data_dictionary.csv"
DATA_CLASSIFICATION_PATH: Path = GOVERNANCE_DIR / "data_classification.csv"
QUALITY_RULES_PATH: Path = GOVERNANCE_DIR / "quality_rules.csv"

# --------------------------------------------------------------------------
# Reporting outputs
# --------------------------------------------------------------------------
PROFILE_REPORT_PATH: Path = REPORTS_DIR / "profile_report.json"
ISSUE_REGISTER_PATH: Path = REPORTS_DIR / "issue_register.csv"
QUALITY_SCORECARD_PATH: Path = REPORTS_DIR / "quality_scorecard.json"
RECONCILIATION_REPORT_PATH: Path = REPORTS_DIR / "reconciliation_report.json"
CLEANING_LOG_PATH: Path = REPORTS_DIR / "data_cleaning_log.csv"
PIPELINE_RUN_REPORT_PATH: Path = REPORTS_DIR / "pipeline_run_report.json"

EXCEL_REPORT_PATH: Path = EXCEL_DIR / "olist_data_quality_report.xlsx"

# --------------------------------------------------------------------------
# PostgreSQL connection settings (loaded from environment / .env)
# --------------------------------------------------------------------------
POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB: str = os.getenv("POSTGRES_DB", "olist_analytics")
POSTGRES_USER: str = os.getenv("POSTGRES_USER", "olist_user")
POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")

SQLALCHEMY_DATABASE_URL: str = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# --------------------------------------------------------------------------
# Business-rule constants (used across validation / transform / scoring)
# --------------------------------------------------------------------------
VALID_BRAZIL_STATES = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
}

VALID_ORDER_STATUSES = {
    "delivered", "shipped", "canceled", "unavailable", "invoiced",
    "processing", "created", "approved",
}

# Order statuses for which a missing delivery date is NOT a quality issue
NON_DELIVERY_STATUSES = {"canceled", "unavailable", "invoiced", "processing", "created", "approved"}

# Quality score weighting per dimension (must sum to 1.0)
QUALITY_DIMENSION_WEIGHTS: dict[str, float] = {
    "completeness": 0.20,
    "uniqueness": 0.20,
    "validity": 0.20,
    "consistency": 0.15,
    "referential_integrity": 0.15,
    "timeliness": 0.10,
}

# Logging
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
