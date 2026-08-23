"""
load.py
-------
LOAD layer (STEP 12).

Purpose:
    Build dimension and fact tables from the transformed DataFrames and
    load them into the PostgreSQL `olist_analytics` star schema created by
    sql/create_database.sql and sql/create_tables.sql.

Connects to:
    - transform.py       -> supplies cleaned DataFrames
    - sql/create_tables.sql -> defines the target schema this module writes to
    - config.py             -> SQLALCHEMY_DATABASE_URL
    - reconciliation.py       -> loaded_counts returned here feed the
                                POSTGRESQL reconciliation stage
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from src.config import SQLALCHEMY_DATABASE_URL
from src.logging_setup import get_logger

logger = get_logger(__name__)


def get_engine() -> Engine:
    return create_engine(SQLALCHEMY_DATABASE_URL)


def build_dim_date(orders: pd.DataFrame) -> pd.DataFrame:
    dates = pd.to_datetime(orders["order_purchase_timestamp"]).dropna().dt.normalize().unique()
    dim = pd.DataFrame({"full_date": pd.to_datetime(dates)})
    dim["date_key"] = dim["full_date"].dt.strftime("%Y%m%d").astype(int)
    dim["year"] = dim["full_date"].dt.year
    dim["month"] = dim["full_date"].dt.month
    dim["day"] = dim["full_date"].dt.day
    dim["quarter"] = dim["full_date"].dt.quarter
    dim["day_of_week"] = dim["full_date"].dt.day_name()
    dim["month_name"] = dim["full_date"].dt.month_name()
    return dim.sort_values("date_key").reset_index(drop=True)


def build_dim_customer(customers: pd.DataFrame) -> pd.DataFrame:
    dim = customers.copy().reset_index(drop=True)
    dim.insert(0, "customer_key", dim.index + 1)
    return dim


def build_dim_product(products: pd.DataFrame) -> pd.DataFrame:
    dim = products.copy().reset_index(drop=True)
    dim.insert(0, "product_key", dim.index + 1)
    return dim


def build_dim_seller(sellers: pd.DataFrame) -> pd.DataFrame:
    dim = sellers.copy().reset_index(drop=True)
    dim.insert(0, "seller_key", dim.index + 1)
    return dim


def build_dim_location(geolocation_lookup: pd.DataFrame) -> pd.DataFrame:
    dim = geolocation_lookup.copy().reset_index(drop=True)
    dim.insert(0, "location_key", dim.index + 1)
    return dim


def build_fact_sales(
    order_items: pd.DataFrame,
    orders: pd.DataFrame,
    dim_customer: pd.DataFrame,
    dim_product: pd.DataFrame,
    dim_seller: pd.DataFrame,
    dim_date: pd.DataFrame,
) -> pd.DataFrame:
    fact = order_items.merge(
        orders[["order_id", "customer_id", "order_status", "order_purchase_timestamp"]],
        on="order_id", how="left",
    )
    fact = fact.merge(dim_customer[["customer_id", "customer_key"]], on="customer_id", how="left")
    fact = fact.merge(dim_product[["product_id", "product_key"]], on="product_id", how="left")
    fact = fact.merge(dim_seller[["seller_id", "seller_key"]], on="seller_id", how="left")

    fact["order_date"] = pd.to_datetime(fact["order_purchase_timestamp"]).dt.normalize()
    fact["date_key"] = fact["order_date"].dt.strftime("%Y%m%d")
    fact["date_key"] = pd.to_numeric(fact["date_key"], errors="coerce")

    fact["order_key"] = fact["order_id"].astype("category").cat.codes + 1
    fact["total_value"] = fact["price"] + fact["freight_value"]

    cols = [
        "order_key", "order_id", "order_item_id", "customer_key", "product_key",
        "seller_key", "date_key", "order_status", "price", "freight_value", "total_value",
    ]
    return fact[cols].reset_index(drop=True)


def load_dataframe(df: pd.DataFrame, table_name: str, engine: Engine, if_exists: str = "replace") -> int:
    df.to_sql(table_name, engine, if_exists=if_exists, index=False, method="multi", chunksize=5000)
    logger.info("Loaded %d rows into PostgreSQL table '%s'", len(df), table_name)
    return len(df)


def run_load(processed: dict[str, pd.DataFrame], engine: Engine | None = None) -> dict[str, int]:
    """
    Build the star schema tables from processed DataFrames and load them
    into PostgreSQL. Returns a dict of {table_name: row_count_loaded} used
    by reconciliation.py for the RAW -> TRANSFORMED -> POSTGRESQL check.
    """
    engine = engine or get_engine()

    dim_date = build_dim_date(processed["orders"])
    dim_customer = build_dim_customer(processed["customers"])
    dim_product = build_dim_product(processed["products"])
    dim_seller = build_dim_seller(processed["sellers"])
    dim_location = build_dim_location(processed.get("geolocation_lookup", pd.DataFrame()))

    fact_sales = build_fact_sales(
        processed["order_items"], processed["orders"],
        dim_customer, dim_product, dim_seller, dim_date,
    )

    loaded_counts: dict[str, int] = {}
    loaded_counts["dim_date"] = load_dataframe(dim_date, "dim_date", engine)
    loaded_counts["dim_customer"] = load_dataframe(dim_customer, "dim_customer", engine)
    loaded_counts["dim_product"] = load_dataframe(dim_product, "dim_product", engine)
    loaded_counts["dim_seller"] = load_dataframe(dim_seller, "dim_seller", engine)
    if not dim_location.empty:
        loaded_counts["dim_location"] = load_dataframe(dim_location, "dim_location", engine)
    loaded_counts["fact_sales"] = load_dataframe(fact_sales, "fact_sales", engine)

    # Also load governance / operational-control tables so Power BI Dashboard 2
    # can query them directly from PostgreSQL rather than flat files.
    for name in ("orders", "order_items", "payments", "reviews", "products", "customers", "sellers"):
        if name in processed:
            loaded_counts[f"stg_{name}"] = load_dataframe(processed[name], f"stg_{name}", engine)

    return loaded_counts


if __name__ == "__main__":
    from src.extract import extract_all
    from src.transform import run_transformation

    raw = extract_all()
    clean = run_transformation(raw)
    counts = run_load(clean)
    print(counts)
