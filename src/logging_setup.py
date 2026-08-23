"""
logging_setup.py
-----------------
Provides a single get_logger() function so every module logs consistently
instead of using scattered print statements (Implementation Rule #9).
"""

from __future__ import annotations

import logging
import sys

from src.config import LOG_FORMAT, LOG_LEVEL


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(LOG_LEVEL)
        logger.propagate = False
    return logger
