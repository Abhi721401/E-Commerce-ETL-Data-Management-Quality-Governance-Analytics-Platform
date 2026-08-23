# Power BI Dashboard Specification

This document specifies both Power BI dashboards, including which
PostgreSQL table/query feeds each visual. Screenshots are not included —
build these dashboards by connecting Power BI Desktop to the
`olist_analytics` PostgreSQL database using **Get Data → PostgreSQL
database** and pointing at the host/port/db defined in `.env`.

---

## Dashboard 1 — Business Analytics

| KPI Card               | Source (table / query)                                   |
|-------------------------|-----------------------------------------------------------|
| Revenue                  | `fact_sales` → `SUM(total_value)`                         |
| Orders                    | `fact_sales` → `COUNT(DISTINCT order_id)`                 |
| Customers                  | `dim_customer` → `COUNT(DISTINCT customer_unique_id)`     |
| Average Order Value         | `sql/analytics.sql` query A3                              |
| Late Delivery %              | `sql/analytics.sql` query A7                              |

| Visual                         | Source                                                    |
|----------------------------------|------------------------------------------------------------|
| Monthly revenue trend (line)      | `sql/analytics.sql` query A2, joined `fact_sales` + `dim_date` |
| Revenue by category (bar)          | `sql/analytics.sql` query A4                               |
| Revenue by state (map)              | `sql/analytics.sql` query A5, joined `dim_customer`        |
| Order status (donut)                 | `sql/analytics.sql` query A8, `stg_orders`                 |
| Delivery performance (gauge/KPI)       | `sql/analytics.sql` query A7                                |
| Top sellers / categories (bar/table)     | `sql/analytics.sql` query A6 / A4                            |

---

## Dashboard 2 — Data Quality & Governance (primary dashboard)

| KPI Card                       | Source (table / query)                                       |
|-----------------------------------|-----------------------------------------------------------------|
| Overall Data Quality Score          | `reports/quality_scorecard.json` → `overall_score_pct` (load as `quality_scorecard` table) |
| Records Processed                    | `reports/pipeline_run_report.json` → `total_records_processed` |
| Quality Issues                        | `issue_register` → `COUNT(*) WHERE affected_records > 0`       |
| Critical Issues                        | `issue_register` → `COUNT(*) WHERE severity='Critical' AND status='Open'` |
| Open Issues                             | `issue_register` → `COUNT(*) WHERE status='Open'`                |
| Resolution Rate                          | `issue_register` → `resolved / total * 100`                       |

| Visual                                  | Source                                                          |
|--------------------------------------------|--------------------------------------------------------------------|
| Quality score by dataset (bar)                | `quality_scorecard` table — query B7 in `sql/analytics.sql`         |
| Quality score by dimension (radar/bar)          | `reports/quality_scorecard.json` → `overall_dimension_scores_pct`   |
| Issues by severity (bar)                          | `sql/analytics.sql` query B4                                        |
| Issues by dataset (bar)                             | `sql/analytics.sql` query B5                                        |
| Open vs. resolved issues (donut)                      | `sql/analytics.sql` query B6                                        |
| Missing-value trend (line, per pipeline run)             | `reports/pipeline_run_report.json` history (append each run to a `pipeline_run_history` table for trending) |
| Duplicate trend (line, per pipeline run)                   | Same as above, sourced from `reconciliation_checks` history          |
| Referential-integrity failures (table)                        | `issue_register` filtered to `dimension = 'referential_integrity'`     |
| Reconciliation status (matrix, PASS/WARNING/FAIL)                | `sql/analytics.sql` query B8, `reconciliation_checks` table              |

### Loading the JSON/CSV outputs into PostgreSQL for Power BI

`issue_register.csv`, `quality_scorecard.json`, and
`reconciliation_report.json` are pipeline outputs in `reports/`. To make
them queryable from Power BI via the same PostgreSQL connection (rather
than juggling two data sources), load them as tables:

```python
import pandas as pd
from src.load import get_engine

engine = get_engine()
pd.read_csv("reports/issue_register.csv").to_sql("issue_register", engine, if_exists="replace", index=False)
```

A similar flattening step converts `quality_scorecard.json` and
`reconciliation_report.json` into `quality_scorecard` and
`reconciliation_checks` tables. This keeps Power BI's data model single-
source (PostgreSQL only), which is the recommended approach for a
production-style BI layer.
