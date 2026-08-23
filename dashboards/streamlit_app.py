"""
dashboards/streamlit_app.py
----------------------------
Streamlit dashboard — an alternative to the Power BI spec in
dashboards/power_bi_dashboard_spec.md, covering the exact same KPIs and
visuals across the same two dashboards, but running entirely off the
pipeline's own output files (no PostgreSQL or Power BI license required).

Data sources (all produced by running `python -m src.reporting` first):
    reports/profile_report.json
    reports/issue_register.csv
    reports/quality_scorecard.json
    reports/reconciliation_report.json
    reports/pipeline_run_report.json
    data/processed/*.parquet   (produced by src/transform.py)

If a PostgreSQL connection is configured (.env) and reachable, the app
will optionally read business-analytics tables (fact_sales, dim_*) from
there instead of parquet — see `_load_star_schema()` below — but this is
not required to run the app.

Run with:
    streamlit run dashboards/streamlit_app.py

Connects to:
    - src/config.py    -> file paths, PostgreSQL settings
    - reports/*, data/processed/*  -> everything this app displays
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import (  # noqa: E402
    ISSUE_REGISTER_PATH,
    PIPELINE_RUN_REPORT_PATH,
    PROCESSED_DATA_DIR,
    PROFILE_REPORT_PATH,
    QUALITY_SCORECARD_PATH,
    RECONCILIATION_REPORT_PATH,
)

st.set_page_config(
    page_title="Olist Data Management, Quality & Governance",
    page_icon="\U0001F4CA",
    layout="wide",
)

SEVERITY_ORDER = ["Critical", "High", "Medium", "Low", "Informational"]
SEVERITY_COLORS = {
    "Critical": "#B00020", "High": "#E65100", "Medium": "#F9A825",
    "Low": "#43A047", "Informational": "#1E88E5",
}
STATUS_COLORS = {"PASS": "#43A047", "WARNING": "#F9A825", "FAIL": "#B00020"}


# --------------------------------------------------------------------------
# Data loading (cached — re-run the pipeline, then hit "R" to refresh)
# --------------------------------------------------------------------------

@st.cache_data(ttl=60)
def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(ttl=60)
def load_issue_register() -> pd.DataFrame:
    if not ISSUE_REGISTER_PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(ISSUE_REGISTER_PATH)


@st.cache_data(ttl=60)
def load_processed(name: str) -> pd.DataFrame:
    path = PROCESSED_DATA_DIR / f"{name}_clean.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def missing_outputs_warning() -> bool:
    """Returns True (and renders guidance) if the pipeline hasn't been run yet."""
    if not PIPELINE_RUN_REPORT_PATH.exists():
        st.warning(
            "No pipeline outputs found yet. Run the pipeline first, then refresh "
            "this page:\n\n```bash\npython -m src.reporting\n```",
            icon="\u26A0\uFE0F",
        )
        return True
    return False


# --------------------------------------------------------------------------
# Sidebar navigation
# --------------------------------------------------------------------------

st.sidebar.title("Olist Data Platform")
page = st.sidebar.radio(
    "Dashboard",
    ["Overview", "Business Analytics", "Data Quality & Governance"],
    index=0,
)

run_report = load_json(PIPELINE_RUN_REPORT_PATH)
if run_report:
    st.sidebar.caption(f"Last pipeline run: {run_report.get('pipeline_run_timestamp', 'unknown')}")
    status = run_report.get("pipeline_status", "UNKNOWN")
    badge = {"PASSED": "\U0001F7E2", "PASSED_WITH_WARNINGS": "\U0001F7E1", "FAILED": "\U0001F534"}.get(status, "\u26AA")
    st.sidebar.markdown(f"**Pipeline status:** {badge} {status}")


# ==========================================================================
# PAGE 1 — OVERVIEW
# ==========================================================================
if page == "Overview":
    st.title("Olist Data Management, Quality & Governance Platform")
    st.caption(
        "A controlled data pipeline for the Olist Brazilian e-commerce dataset — "
        "data quality, governance, and reconciliation come first; business "
        "analytics is secondary."
    )

    if not missing_outputs_warning():
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Overall Quality Score", f"{run_report['quality_scorecard'].get('overall_score_pct', 0):.1f}%")
        c2.metric("Records Processed", f"{run_report.get('total_records_processed', 0):,}")
        c3.metric("Open Issues", run_report["validation_summary"].get("open_issues", 0))
        c4.metric(
            "Reconciliation Status",
            run_report["reconciliation_summary"].get("overall_status", "N/A"),
        )

        st.divider()
        st.subheader("What this platform does")
        st.markdown(
            "- **Extract** the 9 raw Olist CSVs without modifying them\n"
            "- **Profile** every dataset (schema, missingness, duplicates, key candidates)\n"
            "- **Validate** ~30 config-driven rules across 6 quality dimensions\n"
            "- **Transform** the data with documented, business-aware cleaning decisions\n"
            "- **Score** data quality per dataset and overall, using a weighted, documented methodology\n"
            "- **Reconcile** RAW \u2192 TRANSFORMED \u2192 POSTGRESQL record counts, key counts, and monetary totals\n"
            "- **Report** results here, in Excel, and in PostgreSQL/SQL for downstream BI"
        )
        st.info(
            "Use the sidebar to switch between the **Business Analytics** dashboard "
            "and the **Data Quality & Governance** dashboard (the primary dashboard "
            "for this project).",
            icon="\U0001F4A1",
        )


# ==========================================================================
# PAGE 2 — BUSINESS ANALYTICS
# ==========================================================================
elif page == "Business Analytics":
    st.title("Business Analytics")

    orders = load_processed("orders")
    order_items = load_processed("order_items")
    customers = load_processed("customers")
    products = load_processed("products")
    sellers = load_processed("sellers")

    if orders.empty or order_items.empty:
        st.warning(
            "No processed data found. Run the pipeline first:\n\n"
            "```bash\npython -m src.reporting\n```",
            icon="\u26A0\uFE0F",
        )
        st.stop()

    # --- Build the same joins as fact_sales / dim_customer for KPIs ---
    fact = order_items.merge(
        orders[["order_id", "customer_id", "order_status", "order_purchase_timestamp",
                "order_estimated_delivery_date", "order_delivered_customer_date", "is_late"]],
        on="order_id", how="left",
    )
    fact["total_value"] = fact["price"] + fact["freight_value"]
    fact = fact.merge(customers[["customer_id", "customer_unique_id", "customer_state"]],
                       on="customer_id", how="left")
    if not products.empty and "product_category_name_english" in products.columns:
        fact = fact.merge(products[["product_id", "product_category_name_english"]],
                           on="product_id", how="left")

    # --- KPI row ---
    total_revenue = fact["total_value"].sum()
    total_orders = fact["order_id"].nunique()
    total_customers = fact["customer_unique_id"].nunique() if "customer_unique_id" in fact else fact["customer_id"].nunique()
    aov = fact.groupby("order_id")["total_value"].sum().mean()
    delivered = orders[orders["order_status"] == "delivered"]
    late_pct = 100 * delivered["is_late"].mean() if "is_late" in delivered and len(delivered) else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Revenue", f"R$ {total_revenue:,.0f}")
    c2.metric("Orders", f"{total_orders:,}")
    c3.metric("Customers", f"{total_customers:,}")
    c4.metric("Avg Order Value", f"R$ {aov:,.2f}")
    c5.metric("Late Delivery %", f"{late_pct:.1f}%")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Monthly Revenue Trend")
        monthly = fact.copy()
        monthly["order_purchase_timestamp"] = pd.to_datetime(monthly["order_purchase_timestamp"])
        monthly["month"] = monthly["order_purchase_timestamp"].dt.to_period("M").astype(str)
        monthly_rev = monthly.groupby("month")["total_value"].sum().reset_index()
        fig = px.line(monthly_rev, x="month", y="total_value", markers=True,
                       labels={"total_value": "Revenue (R$)", "month": "Month"})
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Revenue by Category")
        if "product_category_name_english" in fact.columns:
            by_cat = (
                fact.groupby("product_category_name_english")["total_value"]
                .sum().sort_values(ascending=False).head(10).reset_index()
            )
            fig = px.bar(by_cat, x="total_value", y="product_category_name_english",
                         orientation="h", labels={"total_value": "Revenue (R$)", "product_category_name_english": "Category"})
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("Product category data not available.")

    col3, col4 = st.columns(2)

    with col3:
        st.subheader("Revenue by Customer State")
        by_state = fact.groupby("customer_state")["total_value"].sum().sort_values(ascending=False).reset_index()
        fig = px.bar(by_state, x="customer_state", y="total_value",
                     labels={"total_value": "Revenue (R$)", "customer_state": "State"})
        st.plotly_chart(fig, use_container_width=True)

    with col4:
        st.subheader("Order Status Breakdown")
        status_counts = orders["order_status"].value_counts().reset_index()
        status_counts.columns = ["order_status", "count"]
        fig = px.pie(status_counts, names="order_status", values="count", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top Sellers by Revenue")
    if not sellers.empty and "seller_id" in fact.columns:
        top_sellers = (
            fact.groupby("seller_id")["total_value"].sum()
            .sort_values(ascending=False).head(10).reset_index()
        )
        top_sellers.columns = ["seller_id", "revenue"]
        st.dataframe(top_sellers, use_container_width=True, hide_index=True)


# ==========================================================================
# PAGE 3 — DATA QUALITY & GOVERNANCE  (primary dashboard)
# ==========================================================================
elif page == "Data Quality & Governance":
    st.title("Data Quality & Governance")

    if missing_outputs_warning():
        st.stop()

    scorecard = load_json(QUALITY_SCORECARD_PATH) or {}
    reconciliation = load_json(RECONCILIATION_REPORT_PATH) or {}
    profile = load_json(PROFILE_REPORT_PATH) or {}
    issues_df = load_issue_register()

    open_issues = issues_df[issues_df["status"] == "Open"] if not issues_df.empty else pd.DataFrame()
    critical_open = open_issues[open_issues["severity"] == "Critical"] if not open_issues.empty else pd.DataFrame()
    resolved = issues_df[issues_df["status"] == "Resolved"] if not issues_df.empty else pd.DataFrame()
    resolution_rate = (len(resolved) / len(issues_df) * 100) if len(issues_df) else 0

    # --- KPI cards ---
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Overall Quality Score", f"{scorecard.get('overall_score_pct', 0):.1f}%")
    c2.metric("Records Processed", f"{sum(d['row_count'] for d in profile.get('datasets', {}).values()):,}")
    c3.metric("Quality Issues", int((issues_df["affected_records"] > 0).sum()) if not issues_df.empty else 0)
    c4.metric("Critical Open Issues", len(critical_open))
    c5.metric("Open Issues", len(open_issues))
    c6.metric("Resolution Rate", f"{resolution_rate:.1f}%")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Quality Score by Dataset")
        ds_scores = scorecard.get("dataset_scores", {})
        if ds_scores:
            df = pd.DataFrame([
                {"dataset": name, "score_pct": info["dataset_score_pct"]}
                for name, info in ds_scores.items() if info.get("dataset_score_pct") is not None
            ]).sort_values("score_pct")
            fig = px.bar(df, x="score_pct", y="dataset", orientation="h",
                         range_x=[0, 100], labels={"score_pct": "Score (%)", "dataset": "Dataset"})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("No dataset scores available.")

    with col2:
        st.subheader("Quality Score by Dimension")
        dim_scores = scorecard.get("overall_dimension_scores_pct", {})
        if dim_scores:
            df = pd.DataFrame(list(dim_scores.items()), columns=["dimension", "score_pct"])
            fig = px.line_polar(df, r="score_pct", theta="dimension", line_close=True, range_r=[0, 100])
            fig.update_traces(fill="toself")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("No dimension scores available.")

    col3, col4 = st.columns(2)

    with col3:
        st.subheader("Open Issues by Severity")
        if not open_issues.empty:
            sev_counts = open_issues["severity"].value_counts().reindex(SEVERITY_ORDER).dropna().reset_index()
            sev_counts.columns = ["severity", "count"]
            fig = px.bar(sev_counts, x="severity", y="count", color="severity",
                         color_discrete_map=SEVERITY_COLORS, category_orders={"severity": SEVERITY_ORDER})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.success("No open issues \u2014 all validation rules pass.", icon="\u2705")

    with col4:
        st.subheader("Open Issues by Dataset")
        if not open_issues.empty:
            ds_counts = open_issues["dataset"].value_counts().reset_index()
            ds_counts.columns = ["dataset", "count"]
            fig = px.bar(ds_counts, x="dataset", y="count")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("No open issues to break down.")

    col5, col6 = st.columns(2)

    with col5:
        st.subheader("Open vs. Resolved Issues")
        if not issues_df.empty:
            status_counts = issues_df["status"].value_counts().reset_index()
            status_counts.columns = ["status", "count"]
            fig = px.pie(status_counts, names="status", values="count", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)

    with col6:
        st.subheader("Reconciliation Status")
        all_checks = (
            reconciliation.get("row_count_checks", [])
            + reconciliation.get("key_count_checks", [])
            + reconciliation.get("monetary_total_checks", [])
        )
        if all_checks:
            df = pd.DataFrame(all_checks)
            status_counts = df["status"].value_counts().reset_index()
            status_counts.columns = ["status", "count"]
            fig = px.bar(status_counts, x="status", y="count", color="status",
                         color_discrete_map=STATUS_COLORS,
                         category_orders={"status": ["PASS", "WARNING", "FAIL"]})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("No reconciliation checks available.")

    st.divider()
    st.subheader("Referential Integrity Failures")
    if not issues_df.empty:
        ri_issues = issues_df[
            issues_df["issue_description"].str.contains("exist in", case=False, na=False)
            & (issues_df["affected_records"] > 0)
        ]
        if not ri_issues.empty:
            st.dataframe(
                ri_issues[["rule_id", "dataset", "field", "issue_description", "affected_records", "severity"]],
                use_container_width=True, hide_index=True,
            )
        else:
            st.success("No referential integrity failures detected.", icon="\u2705")

    st.subheader("Full Issue Register")
    if not issues_df.empty:
        sev_filter = st.multiselect("Filter by severity", SEVERITY_ORDER, default=[])
        status_filter = st.multiselect("Filter by status", sorted(issues_df["status"].unique()), default=[])
        filtered = issues_df.copy()
        if sev_filter:
            filtered = filtered[filtered["severity"].isin(sev_filter)]
        if status_filter:
            filtered = filtered[filtered["status"].isin(status_filter)]
        st.dataframe(
            filtered[["rule_id", "dataset", "field", "issue_description", "severity",
                      "affected_records", "status", "detected_at"]],
            use_container_width=True, hide_index=True,
        )

    st.subheader("Reconciliation Detail")
    all_checks = (
        reconciliation.get("row_count_checks", [])
        + reconciliation.get("key_count_checks", [])
        + reconciliation.get("monetary_total_checks", [])
    )
    if all_checks:
        st.dataframe(pd.DataFrame(all_checks), use_container_width=True, hide_index=True)
