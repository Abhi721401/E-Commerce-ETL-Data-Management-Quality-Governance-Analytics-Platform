# E-Commerce ETL, Data Management, Quality & Governance Analytics Platform

An end-to-end ETL, data quality, governance, reconciliation, and analytics platform built on the Brazilian E-Commerce Public Dataset by Olist.

This project demonstrates how raw operational data is turned into a **validated, governed, reconciled, analytics-ready** data platform using Python, Pandas, PostgreSQL, SQL, Docker, Airflow, automated data-quality controls, and an interactive dashboard.

The primary objective is **data trust and operational reliability** — not exploratory data analysis. Business analytics is a secondary output of the platform, not its purpose.

---

## 📊 Project Highlights

*(Results below are from a full pipeline run against the complete Olist dataset — generated dynamically by the pipeline, not manually entered.)*

| Metric | Result |
|---|---|
| Total records processed | 1,550,922 |
| Data-quality rules evaluated | 30 |
| **Overall data-quality score** | **99.96%** |
| Completeness | 100.00% |
| Uniqueness | 99.71% |
| Validity | 100.00% |
| Referential integrity | 100.00% |
| Timeliness | 99.94% |
| Reconciliation checks | 15 / 15 passed |
| Critical open issues | 0 |
| Open data-quality issues | 6 |
| Resolved issues | 24 |
| Pipeline status | ✅ PASSED |

---

## 📸 Dashboard Preview

### Business Analytics
![Business Analytics Dashboard](dashboards/screenshots/business-analytics-1.png)

### Data Quality & Governance
![Data Quality & Governance Dashboard](dashboards/screenshots/data-quality-1.png)

*(Dashboard built with Streamlit — see [Dashboard](#-dashboard) section. A separate Power BI specification is also included in `dashboards/power_bi_dashboard_spec.md` for teams that prefer a PostgreSQL-connected BI tool, but the screenshots above are from the local Streamlit app, not Power BI.)*

---

## 🧭 Table of Contents

- [Project Overview](#-project-overview)
- [Business Problem](#-business-problem)
- [Architecture](#️-architecture)
- [Technology Stack](#️-technology-stack)
- [Dataset](#-dataset)
- [ETL Pipeline](#-etl-pipeline)
- [Data Quality Framework](#-data-quality-framework)
- [Data Quality Scorecard](#-data-quality-scorecard)
- [Issue Management](#-issue-management)
- [Reconciliation Framework](#-reconciliation-framework)
- [PostgreSQL Data Warehouse](#️-postgresql-data-warehouse)
- [SQL Analytics](#-sql-analytics)
- [Dashboard](#-dashboard)
- [Governance Framework](#-governance-framework)
- [Airflow Orchestration](#️-airflow-orchestration)
- [Testing](#-testing)
- [Docker Deployment](#-docker-deployment)
- [Project Structure](#-project-structure)
- [Setup](#-setup)
- [Generated Reports](#-generated-reports)
- [Project Results](#-project-results)
- [Skills Demonstrated](#-skills-demonstrated)
- [Limitations](#️-limitations)
- [Future Improvements](#-future-improvements)
- [Why This Project Matters](#-why-this-project-matters)

---

## 🎯 Project Overview

Most Olist portfolio projects follow the same pattern:

```
CSV → Pandas → Charts
```

This project takes a different approach. It treats the dataset as if it were an operational data source entering a production data-management environment — every stage exists to answer one question: **can this data be trusted before it's used for a decision?**

```
                 OLIST RAW CSVs
                       │
                       ▼
                    EXTRACT
                       │
                       ▼
                  DATA PROFILING
                       │
                       ▼
                  DATA VALIDATION
                       │
                       ▼
                  TRANSFORMATION
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
       DATA QUALITY          GOVERNANCE
       QUALITY SCORE         DATA DICTIONARY
       ISSUE REGISTER        CLASSIFICATION
             │                   │
             └─────────┬─────────┘
                       ▼
                 RECONCILIATION
                       │
                       ▼
                  POSTGRESQL
                       │
                       ▼
                  STAR SCHEMA
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
       SQL ANALYTICS        CONTROL REPORTS
             │                   │
             └─────────┬─────────┘
                       ▼
                   DASHBOARD
                  (Streamlit)
                       │
                       ▼
                    AIRFLOW
                       │
                       ▼
                    DOCKER
```

**Core principle:** data is not analytics-ready until it has passed validation, quality scoring, governance checks, and reconciliation.

---

## 💼 Business Problem

E-commerce platforms generate data across many operational systems — customers, orders, products, sellers, payments, reviews, order items, geolocation. Before that data can be used for revenue reporting, seller performance, or operational decisions, several questions need answers:

| Dimension | Question |
|---|---|
| Completeness | Are required fields populated? |
| Uniqueness | Are business keys unique at the correct grain? |
| Validity | Are values within acceptable business ranges? |
| Consistency | Are formats, categories, and codes standardized? |
| Referential Integrity | Do foreign keys point to valid parent records? |
| Timeliness | Do timestamps follow physically possible sequences? |
| Reconciliation | Do record counts and financial totals stay consistent across pipeline stages? |

This project implements automated, documented controls for each of these — not a one-off manual check.

---

## 🏗️ Architecture

```
                         OLIST CSV DATA
                              │
                              ▼
                    ┌──────────────────┐
                    │     EXTRACT      │
                    │ Python / Pandas  │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │     PROFILE      │
                    │ Schema / Nulls   │
                    │ Duplicates       │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │    VALIDATE      │
                    │ 30 Quality Rules │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │   TRANSFORM      │
                    │ Cleaning / Logic │
                    └────────┬─────────┘
                             │
                ┌────────────┴────────────┐
                ▼                         ▼
        ┌───────────────┐         ┌────────────────┐
        │ DATA QUALITY  │         │   GOVERNANCE   │
        │ Scorecard     │         │ Dictionary     │
        │ Issue Register│         │ Classification │
        └───────┬───────┘         └───────┬────────┘
                │                         │
                └────────────┬────────────┘
                             ▼
                    ┌──────────────────┐
                    │ RECONCILIATION   │
                    │ RAW → TRANSFORMED│
                    │ → POSTGRES       │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │   POSTGRESQL     │
                    │   Star Schema    │
                    └────────┬─────────┘
                             │
                ┌────────────┴────────────┐
                ▼                         ▼
        ┌───────────────┐         ┌────────────────┐
        │ SQL ANALYTICS │         │ CONTROL REPORTS│
        └───────┬───────┘         └───────┬────────┘
                │                         │
                └────────────┬────────────┘
                             ▼
                        STREAMLIT
                       DASHBOARD
                             │
                             ▼
                          AIRFLOW
                             │
                             ▼
                           DOCKER
```

---

## 🛠️ Technology Stack

**Programming & Data Processing**
Python · Pandas · NumPy · PyArrow

**Database & SQL**
PostgreSQL · SQLAlchemy · psycopg2 · SQL

**Data Quality & Governance**
Config-driven validation rules · data-quality scorecards · issue management · data dictionary · data classification · referential-integrity controls · reconciliation controls

**Orchestration & Deployment**
Apache Airflow · Docker · Docker Compose

**Reporting & Analytics**
SQL analytics · Excel (openpyxl) · Streamlit dashboard · Power BI specification

**Testing**
Pytest

---

## 📦 Dataset

**Brazilian E-Commerce Public Dataset by Olist**
Source: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

Nine CSV files covering ~99,441 orders from the Brazilian e-commerce marketplace:

```
olist_customers_dataset.csv
olist_geolocation_dataset.csv
olist_order_items_dataset.csv
olist_order_payments_dataset.csv
olist_order_reviews_dataset.csv
olist_orders_dataset.csv
olist_products_dataset.csv
olist_sellers_dataset.csv
product_category_name_translation.csv
```

Records processed per dataset:

```
Customers                99,441
Geolocation            1,000,163
Order Items              112,650
Payments                 103,886
Reviews                   99,224
Orders                    99,441
Products                  32,951
Sellers                    3,095
Category Translation          71
──────────────────────────────────
Total                  1,550,922
```

---

## 🔄 ETL Pipeline

**Extract** — raw CSVs are loaded without modifying the source layer (`data/raw/` is never written to).

**Profile** — every dataset is profiled for schema, data types, missing values, duplicate records, key uniqueness, and basic distributions.

**Validate** — data is checked against 30 configurable quality rules (`governance/quality_rules.csv`).

**Transform** — standardization, business-rule-aware missingness handling, composite-key construction, type conversion, category mapping, and analytical dimension construction (`src/transform.py`).

**Load** — validated data is loaded into PostgreSQL using a star-schema design (`src/load.py`).

**Report** — the pipeline generates machine-readable control reports:

```
reports/
├── data_cleaning_log.csv
├── issue_register.csv
├── pipeline_run_report.json
├── profile_report.json
├── quality_scorecard.json
└── reconciliation_report.json
```

---

## 🧪 Data Quality Framework

The validation engine evaluates 30 configurable rules across six dimensions.

| Dimension | Purpose | Result |
|---|---|---|
| Completeness | Required fields populated | 100.00% |
| Uniqueness | Key uniqueness at correct grain | 99.71% |
| Validity | Values satisfy defined constraints | 100.00% |
| Referential Integrity | Foreign keys resolve correctly | 100.00% |
| Timeliness | Event timestamps are logically ordered | 99.94% |

### Business-aware validation

The project deliberately avoids simplistic cleaning such as `df.dropna()` across a whole table. Missingness is interpreted according to business context:

- Review comments are optional — a missing comment is not a defect.
- Delivery dates are only required for orders with status `delivered`.
- Product physical attributes (weight, dimensions) are never blindly replaced with zero.
- Order-item and payment sequence numbers are validated as **composite keys** (`order_id` + sequence), not standalone primary keys.
- Geolocation duplication is handled through a documented, deterministic analytical lookup rather than modifying the raw table.

---

## 📊 Data Quality Scorecard

**Overall quality score: 99.96%**

```
Completeness             100.00%
Validity                 100.00%
Referential Integrity    100.00%
Timeliness                99.94%
Uniqueness                99.71%
──────────────────────────────
Overall                   99.96%
```

The score is calculated by `src/quality_score.py` from actual validation results — it is not manually entered.

---

## 🚨 Issue Management

Every validation rule produces an issue-register record. Schema:

```
rule_id, dataset, field, issue_description, severity,
affected_records, detected_at, status, resolution, resolved_at
```

**Current results**

```
Total rules evaluated       30
Resolved issues             24
Open issues                  6
Critical open issues         0
```

Open issues by severity:

```
High       2
Medium     2
Low        2
```

Open issues by dataset:

```
Orders       2
Products     2
Payments     1
Reviews      1
```

This reflects a core governance principle: **data quality problems are tracked as operational issues, not silently removed during cleaning.**

### Example issues identified

- **Delivery timestamp validation** — a small number of records violated the expected chronological relationship between purchase and carrier-delivery timestamps.
- **Delivered-order completeness** — a small number of `delivered`-status orders were missing a customer delivery timestamp.
- **Product category integrity** — a small number of `product_category_name` values did not resolve against the category-translation reference table.

Each is retained in the issue register with severity and affected-record counts — see `reports/issue_register.csv`.

---

## 🔁 Reconciliation Framework

Source-to-target reconciliation across:

```
RAW → TRANSFORMED → POSTGRESQL
```

Controls: record counts, distinct key counts, and monetary totals (price, freight, payment value). Each check is classified **PASS / WARNING / FAIL** against documented variance thresholds.

**Actual result**

```
Total checks      15
Passed             15
Warnings            0
Failed              0
Overall status:  PASS
```

A `FAIL` status is designed to stop downstream orchestration (Airflow) rather than let potentially incorrect data continue through the pipeline.

---

## 🗄️ PostgreSQL Data Warehouse

Validated data is organized into a star schema (`sql/create_tables.sql`).

**Fact table — `fact_sales`** (grain: one row per order item)
```
order_key, order_id, order_item_id, customer_key, product_key,
seller_key, date_key, order_status, price, freight_value, total_value
```

**Dimensions**
```
dim_customer, dim_product, dim_seller, dim_date, dim_location
```

Foreign-key relationships enforce database-level referential integrity between the fact and dimension tables.

---

## 📈 SQL Analytics

`sql/analytics.sql` — production-style SQL for both business and governance analytics.

**Business Analytics:** total revenue, monthly revenue trend, order volume, average order value, revenue by category, revenue by state, seller performance, delivery performance, order-status distribution.

**Governance Analytics:** missing-value rates, duplicate-key checks, validation failures, issues by severity/dataset, open vs. resolved issues, quality score by dataset, reconciliation status.

---

## 📺 Dashboard

Results are viewed through an interactive **Streamlit** app (`dashboards/streamlit_app.py`) — no PostgreSQL connection or BI license required, since it reads directly from the pipeline's own output files.

```bash
python -m src.reporting              # generate the reports first
streamlit run dashboards/streamlit_app.py
```

### Business Analytics view

| KPI | Result |
|---|---|
| Revenue | R$ 15.84M |
| Orders | 98,666 |
| Customers | 95,420 |
| Average Order Value | R$ 160.58 |
| Late Delivery Rate | 6.8% |

Includes: monthly revenue trend, revenue by product category, revenue by customer state, order-status distribution, top sellers by revenue, delivery performance.

### Data Quality & Governance view (primary dashboard)

Overall quality score · records processed · quality issues · critical open issues · open vs. resolved issues · resolution rate · quality by dataset · quality by dimension · issues by severity · issues by dataset · reconciliation status · referential-integrity failures · full filterable issue register · reconciliation detail.

This lets a reviewer drill from a single headline number down to a specific rule:

```
Overall Quality Score → Dataset / Dimension → Issue Severity → Specific Rule → Affected Records
```

### Reconciliation detail (example)

```
Dataset         Raw Count    Transformed Count    Variance    Status
---------------------------------------------------------------------
customers          99,441          99,441            0%       PASS
orders              99,441          99,441            0%       PASS
order_items         112,650         112,650            0%       PASS
payments            103,886         103,886            0%       PASS
reviews              99,224          99,224            0%       PASS
products             32,951          32,951            0%       PASS
sellers               3,095           3,095            0%       PASS
```

A separate **Power BI specification** (`dashboards/power_bi_dashboard_spec.md`) documents which PostgreSQL table/query feeds each visual, for teams that prefer a PostgreSQL-connected BI tool instead of Streamlit. It is a specification only — no Power BI report is included in this repository.

---

## 🧾 Governance Framework

**Data Dictionary** — `governance/data_dictionary.csv`
Field definitions, data types, nullability, business definitions, data ownership, classification, and the quality rule(s) governing each field.

**Data Classification** — `governance/data_classification.csv`
Simulated classifications (Public / Internal / Confidential / Sensitive). **These are illustrative, project-level classifications and do not represent the internal policy of any real organization** — see `governance/README_GOVERNANCE.md` for the explicit disclaimer.

**Quality Rules** — `governance/quality_rules.csv`
The configuration layer the validation engine reads from. Adding or modifying a rule is a config change, not a code change.

---

## ⚙️ Airflow Orchestration

`dags/olist_etl_dag.py`:

```
extract → profile → validate → transform → quality_score
        → reconcile → load_postgres → generate_report
```

Operational controls: retry handling on the PostgreSQL load task, reconciliation-failure gating, critical-issue failure conditions, sequential task dependencies, automated report generation. Deployed with a lightweight single-node `LocalExecutor`.

---

## 🧪 Testing

```bash
pytest tests/ -v
```

Coverage: duplicate detection, null validation, invalid-value detection, referential integrity, date/timestamp logic, transformation correctness, row-count preservation, reconciliation PASS/FAIL behavior — both positive and negative cases.

---

## 🐳 Docker Deployment

```bash
cp .env.example .env                     # set a real POSTGRES_PASSWORD
docker compose up -d postgres             # data warehouse
docker compose run --rm etl               # run the pipeline once
docker compose up -d streamlit            # dashboard at http://localhost:8501
docker compose up -d airflow-init airflow-webserver airflow-scheduler
docker compose ps
```

Services: PostgreSQL · ETL · Streamlit · Airflow Init · Airflow Scheduler · Airflow Webserver.

---

## 📁 Project Structure

```
olist-data-governance/
│
├── data/
│   ├── raw/                     # place the 9 Olist CSVs here (untouched by the pipeline)
│   └── processed/                # cleaned parquet outputs
│
├── src/
│   ├── config.py
│   ├── extract.py
│   ├── profile.py
│   ├── validation.py
│   ├── transform.py
│   ├── quality_score.py
│   ├── reconciliation.py
│   ├── load.py
│   ├── reporting.py
│   └── logging_setup.py
│
├── sql/
│   ├── create_database.sql
│   ├── create_tables.sql
│   ├── transformations.sql
│   └── analytics.sql
│
├── governance/
│   ├── quality_rules.csv
│   ├── data_dictionary.csv
│   ├── data_classification.csv
│   └── README_GOVERNANCE.md
│
├── reports/                      # generated by the pipeline (not committed)
│   ├── data_cleaning_log.csv
│   ├── issue_register.csv
│   ├── pipeline_run_report.json
│   ├── profile_report.json
│   ├── quality_scorecard.json
│   └── reconciliation_report.json
│
├── dashboards/
│   ├── streamlit_app.py
│   ├── power_bi_dashboard_spec.md
│   └── screenshots/
│       ├── business-analytics-1.png
│       ├── business-analytics-2.png
│       ├── data-quality-1.png
│       ├── data-quality-2.png
│       ├── issue-register.png
│       └── reconciliation.png
│
├── excel/
│   └── generate_excel_report.py
│
├── dags/
│   └── olist_etl_dag.py
│
├── notebooks/
│   └── exploration.ipynb
│
├── tests/
│   ├── test_validation.py
│   ├── test_transform.py
│   └── test_reconciliation.py
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## 🚀 Setup

### 1. Clone the repository
```bash
git clone https://github.com/Abhi721401/olist-data-governance.git
cd olist-data-governance
```

### 2. Create a virtual environment
```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
```bash
cp .env.example .env
```
Update `.env` with your local database configuration. **Never commit `.env` or real credentials.**

### 5. Add the Olist data
Download from Kaggle and place all nine CSVs in `data/raw/`:
https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

### 6. Run the pipeline
```bash
python -m src.reporting
```

### 7. View the dashboard
```bash
streamlit run dashboards/streamlit_app.py
```

### 8. Generate the Excel report
```bash
python -m excel.generate_excel_report
```

### 9. Run tests
```bash
pytest tests/ -v
```

### 10. PostgreSQL + Docker (optional)
```bash
psql -U postgres -f sql/create_database.sql
psql -U postgres -d olist_analytics -f sql/create_tables.sql
python -m src.load
# or, fully containerized:
docker compose up -d postgres
docker compose run --rm etl
docker compose up -d streamlit
```

---

## 📄 Generated Reports

```
reports/profile_report.json
reports/issue_register.csv
reports/quality_scorecard.json
reports/reconciliation_report.json
reports/data_cleaning_log.csv
reports/pipeline_run_report.json
```

`reports/pipeline_run_report.json` is the primary run summary, e.g.:

```json
{
  "total_records_processed": 1550922,
  "quality_score": 99.96,
  "open_issues": 6,
  "critical_open_issues": 0,
  "reconciliation_status": "PASS",
  "pipeline_status": "PASSED"
}
```

---

## 📌 Project Results

The executed pipeline processed **1.55 million records** across nine Olist datasets, evaluated **30 validation rules**, and achieved **99.96% overall data quality** — 100% completeness, 100% validity, 100% referential integrity, 99.94% timeliness, 99.71% uniqueness.

The reconciliation framework achieved **15/15 PASS** (0 warnings, 0 failures). The issue-management framework logged **24 resolved** and **6 open** issues, with **0 critical open issues**.

This demonstrates that the pipeline does not simply "clean" data — it **measures, documents, governs, and controls** data quality throughout the lifecycle.

---

## 🎯 Skills Demonstrated

**Data Engineering** — ETL development, data transformation, pipeline orchestration, PostgreSQL, Docker, Airflow

**Data Analytics** — SQL, business KPIs, revenue analysis, seller analytics, delivery analytics, dashboard development

**Data Quality** — completeness, uniqueness, validity, consistency, referential integrity, timeliness, quality scoring

**Data Governance** — data dictionary, data classification, data ownership, quality rules, issue management, operational controls

**Data Management** — source-to-target reconciliation, data lineage concepts, control frameworks, exception handling, auditability, automated reporting

---

## ⚠️ Limitations

- The Olist dataset is public and historical.
- Governance classifications (`governance/data_classification.csv`) are simulated for portfolio purposes.
- Data owners listed in the data dictionary are illustrative, not real organizational owners.
- Quality thresholds and reconciliation tolerance bands are designed for demonstration.
- This project does not represent the internal data, systems, policies, or processes of any real company.
- Dashboard results are based on the public Olist dataset and the pipeline run that produced them.

---

## 🔮 Future Improvements

- OpenLineage-based data lineage
- Historical quality-score tracking across pipeline runs
- Data-quality trend dashboards
- JSON/SQL-based data contracts and schema-drift detection
- Automated issue-resolution workflows
- CI/CD pipeline validation
- Cloud deployment
- Production database monitoring and reconciliation-failure alerting
- Role-based access control
- Data catalog integration

---

## ⭐ Why This Project Matters

The central question this project answers isn't *"what happened in the Olist data?"* — it's:

**"Can we trust the data enough to make decisions from it?"**

The platform provides evidence through a documented chain:

```
PROFILING → VALIDATION → QUALITY SCORING → GOVERNANCE
→ ISSUE MANAGEMENT → RECONCILIATION → DATABASE INTEGRITY
→ ANALYTICS → REPORTING
```

Relevant to roles such as: **Data Analyst · Data Quality Analyst · Data Management Analyst · Analytics & Metrics Analyst · BI Analyst · Data Governance Analyst · Junior Data Engineer**

---

## 📬 Author

**Abhijnan Das**
M.Sc. Statistics · Data Analytics · Data Science · Data Engineering
GitHub: [github.com/Abhi721401](https://github.com/Abhi721401)
```
