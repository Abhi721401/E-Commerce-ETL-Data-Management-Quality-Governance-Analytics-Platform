# Olist E-Commerce Data Management, Quality & Governance Analytics Platform

A controlled data management pipeline that ensures data is **accurate,
complete, consistent, traceable, governed, and ready for business
analytics** — built on the Brazilian E-Commerce Public Dataset by Olist.

**Business analytics is secondary here. Data quality, governance,
controls, and operational reliability are the primary focus.** This
project is designed to demonstrate the skills required for a data
management / analytics-and-metrics analyst role: data validation, data
integrity, governance, classification, issue management, reconciliation,
SQL, Python, PostgreSQL, Excel, Power BI, and automated operational
controls.

---
## Demo

[▶️ Watch the project demo](https://github.com/user-attachments/assets/b619ca00-fed1-4cd3-ae66-0ee517d2d813)

## Table of Contents

1. [Project Overview](#project-overview)
2. [Business Problem](#business-problem)
3. [Why Data Quality and Governance Matter](#why-data-quality-and-governance-matter)
4. [Role Alignment](#role-alignment)
5. [Architecture](#architecture)
6. [Dataset](#dataset)
7. [Data Model (Star Schema)](#data-model-star-schema)
8. [Data Quality Framework](#data-quality-framework)
9. [Governance Framework](#governance-framework)
10. [Issue Management](#issue-management)
11. [Reconciliation](#reconciliation)
12. [Dashboards](#dashboards)
13. [Orchestration (Airflow)](#orchestration-airflow)
14. [Testing](#testing)
15. [Deployment (Docker)](#deployment-docker)
16. [Project Results](#project-results)
17. [Limitations](#limitations)
18. [Future Improvements](#future-improvements)
19. [Setup & Run Instructions](#setup--run-instructions)

---

## Project Overview

Most public "Olist portfolio projects" are Kaggle-style exploratory
notebooks: load the CSVs, `dropna()`, `drop_duplicates()`, plot a few
charts. This project is deliberately built the opposite way — as a
**controlled data pipeline** with the same structure a data
management/analytics team would run against real operational data:

```
Extract → Profile → Validate → Transform → Quality Score + Governance
        → Reconciliation → PostgreSQL (Star Schema) → SQL Analytics
        → Power BI (Business + Governance dashboards) → Automated Reporting
        → Airflow orchestration → Docker deployment
```

Every cleaning decision is documented. Every quality rule is
config-driven, not hardcoded. Every stage is reconciled against the one
before it. Nothing is fabricated — every number in this repository is
calculated from the actual dataset at pipeline run time.

## Business Problem

An e-commerce marketplace (Olist) aggregates orders across thousands of
independent sellers, multiple carriers, and millions of customer
interactions. Before that data can be trusted for revenue reporting,
seller performance scorecards, or delivery SLAs, someone has to answer:

- Is the data complete? Are required fields actually populated?
- Is it unique — are we double-counting orders or payments?
- Is it valid — are prices, ratings, and state codes within legal bounds?
- Is it consistent — are categories and formats standardized?
- Is it referentially intact — does every order item point to a real
  order, product, and seller?
- Is it timely — do event timestamps happen in a physically possible
  sequence?

This project builds the pipeline, controls, and dashboards that answer
those questions continuously, not as a one-off analysis.

## Why Data Quality and Governance Matter

Bad data doesn't fail loudly — it fails quietly, in a dashboard a VP
trusts, or a reconciliation that's off by 2% and nobody notices until
finance does. A data management/analytics function exists to catch that
before it reaches a decision-maker. This project operationalizes that
responsibility: every raw file is profiled before it's touched, every
transformation is justified and logged, every load is reconciled back to
its source, and every quality issue is tracked to resolution instead of
silently disappearing.

## Role Alignment

| Skill Area                | Where it's demonstrated |
|----------------------------|---------------------------|
| Data management             | `src/extract.py`, `src/config.py`, immutable raw layer |
| Data processing               | `src/transform.py`, `src/load.py` |
| Data validation                 | `src/validation.py`, `governance/quality_rules.csv` |
| Data quality                      | `src/quality_score.py`, `reports/quality_scorecard.json` |
| Data integrity                      | Referential-integrity checks (DQ011–DQ013, DQ017, DQ025, DQ028) |
| Data governance                       | `governance/data_dictionary.csv`, `data_classification.csv` |
| Data classification                     | `governance/data_classification.csv` (simulated) |
| Data issue management                     | `src/reporting.py::write_issue_register`, `reports/issue_register.csv` |
| Data reconciliation                         | `src/reconciliation.py` |
| SQL                                            | `sql/create_tables.sql`, `sql/transformations.sql`, `sql/analytics.sql` |
| Python / Pandas                                  | Entire `src/` package |
| PostgreSQL                                         | Star schema warehouse (`sql/`, `src/load.py`) |
| Excel                                                | `excel/generate_excel_report.py` |
| Power BI                                               | `dashboards/power_bi_dashboard_spec.md` |
| Reporting                                                | `src/reporting.py`, automated `pipeline_run_report.json` |
| Operational controls                                       | Reconciliation PASS/WARNING/FAIL gating, Airflow failure conditions |
| Automation                                                    | `dags/olist_etl_dag.py` |
| Testing                                                         | `tests/` (pytest) |
| Cross-functional / operational thinking                          | Data dictionary ownership, conditional business-rule validation |

## Architecture

```
                    OLIST RAW CSVs
                          │
                          ▼
                    EXTRACT
                  Python / Pandas
                          │
                          ▼
                  DATA PROFILING
          Schema / Missing / Duplicates
                          │
                          ▼
                  DATA VALIDATION
      Completeness / Validity / Consistency
       Uniqueness / Integrity / Timeliness
                          │
                          ▼
                   TRANSFORMATION
              Cleaning + Business Logic
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
       DATA QUALITY             GOVERNANCE
       ISSUE REGISTER           DATA DICTIONARY
       QUALITY SCORE            CLASSIFICATION
              │                       │
              └───────────┬───────────┘
                          ▼
                    RECONCILIATION
                          │
                          ▼
                    POSTGRESQL
                          │
                          ▼
                    STAR SCHEMA
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
        SQL ANALYTICS            CONTROL REPORTS
              │                       │
              └───────────┬───────────┘
                          ▼
                     POWER BI
              ┌───────────┴───────────┐
              ▼                       ▼
       BUSINESS ANALYTICS       DATA GOVERNANCE
          DASHBOARD                DASHBOARD
                          │
                          ▼
                        AIRFLOW
                          │
                          ▼
                       DOCKER
```

## Dataset

**Brazilian E-Commerce Public Dataset by Olist — Kaggle**
Source: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

9 CSV files covering ~99,441 orders placed on the Olist marketplace
between 2016–2018, across customers, sellers, products, payments, order
items, reviews, and geolocation. The dataset is public; this project's
governance framework and classifications are simulated for portfolio
purposes (see [Limitations](#limitations)).

Place the raw files in `data/raw/` before running the pipeline — see
[Setup & Run Instructions](#setup--run-instructions).

## Data Model (Star Schema)

**Fact table:** `fact_sales` (grain = one row per order item)
`order_key, order_id, order_item_id, customer_key, product_key,
seller_key, date_key, order_status, price, freight_value, total_value`

**Dimensions:** `dim_customer`, `dim_product`, `dim_seller`, `dim_date`,
`dim_location` (deduplicated zip-prefix geolocation lookup — see the
geolocation governance decision below).

Full DDL: `sql/create_tables.sql`. Referential integrity is enforced at
the database level via foreign keys from `fact_sales` to each dimension.

## Data Quality Framework

Six dimensions, implemented as a **config-driven rule engine**
(`src/validation.py` + `governance/quality_rules.csv`) rather than
hardcoded per-dataset logic — adding a rule is a CSV edit, not a code
change:

| Dimension | What it checks |
|---|---|
| Completeness | Required fields are non-null (with business-aware exceptions — see below) |
| Uniqueness | Primary/business keys have no duplicates, at the correct grain |
| Validity | Values fall within legal bounds (price > 0, review_score 1–5, valid state codes) |
| Consistency | Standardized casing/formats across text fields |
| Referential Integrity | Every foreign key resolves to a real parent record |
| Timeliness | Event timestamps occur in a physically possible order |

**Business-aware judgment calls baked into the rules, not glossed over:**

- `review_comment_title` / `review_comment_message` are **optional** —
  missing text is never scored as a completeness defect.
- `order_delivered_customer_date` is only flagged missing when
  `order_status = 'delivered'` (rule DQ008). Cancelled/unavailable orders
  legitimately never reach delivery.
- Product physical attributes (`product_weight_g`, dimensions) are never
  imputed with 0 — a NULL weight is not a zero weight.
- `order_item_id` and `payment_sequential` are validated as **composite**
  keys (`order_id` + sequence number), not as standalone primary keys,
  because an order legitimately has multiple items and multiple payments.
- `geolocation` has a large volume of full-row duplicates by design (many
  geographic observations per zip prefix). Rather than blindly
  deduplicating the raw table, a deterministic, documented rule builds a
  one-row-per-zip-prefix analytical lookup (`dim_location`) while the raw
  table itself is left untouched.

Scoring methodology (dimension weights, dataset score, overall score) is
fully documented in `src/quality_score.py`.

## Governance Framework

- **Data dictionary** (`governance/data_dictionary.csv`): every important
  field with its description, type, nullability, business definition,
  data owner, classification, and the quality rule(s) that govern it.
- **Classification** (`governance/data_classification.csv`): simulated
  Public / Internal / Confidential / Sensitive labels with handling
  guidance. **These are project-level simulated classifications, not
  Mastercard's or any organization's real internal scheme** — see
  `governance/README_GOVERNANCE.md` for the explicit disclaimer.
- **Ownership**: each data dictionary entry has an illustrative
  `data_owner` (e.g. "Finance Data Team") to demonstrate accountability
  mapping, not a claim about real organizational structure.
- **Quality rules** (`governance/quality_rules.csv`): the single source
  of truth the validation engine reads from.

## Issue Management

Every validation rule produces an issue-register record — including
passing rules, so the register shows full coverage, not just failures.
Schema: `issue_id, rule_id, dataset, field, issue_description, severity,
affected_records, detected_at, status, resolution, resolved_at`.
Severity levels (Critical/High/Medium/Low/Informational) distinguish real
defects from expected or explainable missingness — see
`DATA-SPECIFIC IMPLEMENTATION CONTEXT` principles baked into
`src/transform.py` and `src/validation.py`. Output: `reports/issue_register.csv`.

## Reconciliation

`src/reconciliation.py` implements source-to-target controls across
**RAW → TRANSFORMED → POSTGRESQL**: record counts, distinct key counts,
and monetary totals (price, freight, payment value), each classified
PASS / WARNING / FAIL against documented variance thresholds
(0.1% / 1%). Output: `reports/reconciliation_report.json`. A `FAIL`
status halts the Airflow DAG rather than silently continuing.

## Dashboards

Two Power BI dashboards, fully specified (including which PostgreSQL
table/query feeds each visual) in `dashboards/power_bi_dashboard_spec.md`:

1. **Business Analytics** — revenue, orders, AOV, delivery performance,
   top categories/sellers.
2. **Data Quality & Governance** (primary dashboard for this project) —
   overall quality score, issues by severity/dataset, open vs. resolved,
   referential-integrity failures, reconciliation status.

No dashboard screenshots are included — build them by connecting Power BI
Desktop to `olist_analytics` per the spec; this avoids fabricating results
that weren't actually produced by a real Power BI session.

## Orchestration (Airflow)

`dags/olist_etl_dag.py` runs: `extract → profile → validate → transform →
quality_score → reconcile → load_postgres → generate_report`. The
`reconcile` and `generate_report` tasks raise `AirflowFailException` when
reconciliation fails or critical issues remain open, so the DAG fails
loudly on a genuine control breach instead of reporting a false "success."
Retries are configured on the PostgreSQL load task for transient
connection issues.

## Testing

`pytest` covers `src/validation.py`, `src/transform.py`, and
`src/reconciliation.py` with both positive and negative cases: duplicate
detection, null validation, invalid values, referential integrity, date
logic, transformation correctness, row-count preservation, and
reconciliation pass/fail behavior. Run with:

```bash
pytest tests/ -v
```

## Deployment (Docker)

`docker-compose.yml` runs PostgreSQL, a single-node Airflow
(LocalExecutor), and the ETL application container. Kept intentionally
minimal for a portfolio project — no CeleryExecutor/Redis. See
[Setup & Run Instructions](#setup--run-instructions).

## Project Results

Populate this section by running the pipeline once against the real
dataset and copying the summary from `reports/pipeline_run_report.json`:

```bash
python -m src.reporting
cat reports/pipeline_run_report.json
```

No numbers are pre-filled here — every result in this repository is
generated dynamically at run time, never fabricated (see
`DATA-SPECIFIC IMPLEMENTATION CONTEXT`, section 19).

## Limitations

- Olist is a **public** e-commerce dataset — not proprietary or
  transactional financial data from any real institution.
- The governance classifications in this project are **simulated** for
  demonstration purposes; they are not Mastercard's (or any
  organization's) actual internal data classification policy.
- This project **is not** Mastercard internal data, systems, or process
  documentation, and makes no claim to be.
- Controls (severity thresholds, reconciliation variance bands, scoring
  weights) are designed to be reasonable and documented for portfolio
  demonstration — they are illustrative, not organization-approved SLAs.

## Future Improvements

- Add data lineage visualization (e.g. OpenLineage) across the DAG.
- Add trend history tables so quality-score and reconciliation-status
  changes can be tracked run-over-run in Power BI (currently each run
  overwrites the prior JSON/CSV snapshot).
- Add a lightweight data-contract layer (e.g. JSON Schema per source
  file) to catch upstream schema drift before extraction.
- Expand the issue register workflow with an actual resolution UI/queue
  instead of a flat CSV.

## Setup & Run Instructions

### 1. Get the data
Download the dataset from Kaggle and place all 9 CSVs in `data/raw/`:
https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

### 2. Local Python setup
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then edit .env with real credentials
```

### 3. Run the full pipeline (extract → report)
```bash
python -m src.reporting
```
This writes `reports/profile_report.json`, `reports/issue_register.csv`,
`reports/quality_scorecard.json`, `reports/reconciliation_report.json`,
`reports/data_cleaning_log.csv`, and `reports/pipeline_run_report.json`.

### 4. Generate the Excel report
```bash
python -m excel.generate_excel_report
```
Output: `excel/olist_data_quality_report.xlsx`.

### 5. Set up PostgreSQL and load the star schema
```bash
# with a local Postgres instance running and .env configured:
psql -U postgres -f sql/create_database.sql
psql -U postgres -d olist_analytics -f sql/create_tables.sql
psql -U postgres -d olist_analytics -f sql/transformations.sql
python -m src.load
```

### 6. Run tests
```bash
pytest tests/ -v
```

### 7. Run everything in Docker
```bash
cp .env.example .env             # set a real POSTGRES_PASSWORD
docker compose up -d postgres
docker compose run --rm etl
docker compose up -d airflow-init airflow-webserver airflow-scheduler
# Airflow UI: http://localhost:8080 (user/pass created by airflow-init: admin/admin)
```

### 8. Connect Power BI
Get Data → PostgreSQL database → host/port/db from `.env` → follow
`dashboards/power_bi_dashboard_spec.md` for which table/query feeds each visual.
