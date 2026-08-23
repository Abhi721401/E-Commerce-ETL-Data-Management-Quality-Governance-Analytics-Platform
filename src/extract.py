"""
extract.py
----------
EXTRACT layer of the pipeline.

Purpose:
    Load the 9 raw Olist CSV files from data/raw/ into pandas DataFrames
    WITHOUT modifying them in any way. This is the immutable source-of-truth
    layer that every downstream stage (profiling, validation, transformation)
    reads from.

Connects to:
    - config.py            -> RAW_DATA_DIR, RAW_FILES
    - profile.py            -> consumes the dict of DataFrames returned here
    - validation.py          -> consumes the same raw DataFrames
    - Airflow DAG (extract task) -> calls extract_all() first in the pipeline
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import RAW_DATA_DIR, RAW_FILES
from src.logging_setup import get_logger

logger = get_logger(__name__)


class MissingSourceFileError(FileNotFoundError):
    """Raised when one or more expected raw CSV files cannot be found."""


def verify_raw_files_exist(raw_dir: Path = RAW_DATA_DIR) -> dict[str, bool]:
    """
    Check that every expected raw file is present in data/raw/.

    Returns:
        dict mapping dataset name -> True/False (file exists)
    """
    status: dict[str, bool] = {}
    for name, filename in RAW_FILES.items():
        path = raw_dir / filename
        exists = path.exists()
        status[name] = exists
        if not exists:
            logger.warning("Missing expected raw file: %s (%s)", filename, path)
    return status


def extract_dataset(name: str, raw_dir: Path = RAW_DATA_DIR) -> pd.DataFrame:
    """
    Load a single raw dataset by its logical name (e.g. 'orders').

    Raises:
        MissingSourceFileError if the file does not exist.
    """
    if name not in RAW_FILES:
        raise KeyError(f"Unknown dataset name '{name}'. Expected one of: {list(RAW_FILES)}")

    path = raw_dir / RAW_FILES[name]
    if not path.exists():
        raise MissingSourceFileError(
            f"Raw source file for '{name}' not found at {path}. "
            f"Place the Olist CSV files in {raw_dir} before running the pipeline."
        )

    df = pd.read_csv(path)
    logger.info("Extracted '%s' from %s -> %d rows, %d columns", name, path.name, len(df), df.shape[1])
    return df


def extract_all(raw_dir: Path = RAW_DATA_DIR, strict: bool = False) -> dict[str, pd.DataFrame]:
    """
    Load all 9 Olist raw datasets.

    Args:
        raw_dir: directory containing the raw CSVs.
        strict: if True, raise immediately when any file is missing.
                if False (default), skip missing files and log a warning
                so the rest of the pipeline can still be inspected/tested.

    Returns:
        dict[str, pd.DataFrame] keyed by logical dataset name
        (customers, geolocation, order_items, payments, reviews,
         orders, products, sellers, category_translation).
    """
    availability = verify_raw_files_exist(raw_dir)
    missing = [name for name, ok in availability.items() if not ok]

    if missing and strict:
        raise MissingSourceFileError(f"Missing required raw files for: {missing}")

    datasets: dict[str, pd.DataFrame] = {}
    for name in RAW_FILES:
        if not availability[name]:
            logger.warning("Skipping extraction of '%s' — file not found.", name)
            continue
        datasets[name] = extract_dataset(name, raw_dir)

    total_rows = sum(len(df) for df in datasets.values())
    logger.info(
        "Extraction complete: %d/%d datasets loaded, %d total rows.",
        len(datasets), len(RAW_FILES), total_rows,
    )
    return datasets


if __name__ == "__main__":
    data = extract_all()
    for name, df in data.items():
        print(f"{name:>22s}: {df.shape[0]:>9,} rows x {df.shape[1]} cols")
