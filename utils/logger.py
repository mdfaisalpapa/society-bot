"""
logger.py

Central logging configuration for Society Bot.

Usage:

from utils.logger import get_logger

logger = get_logger(__name__)

logger.info("Bot started")
logger.warning("Warning")
logger.error("Something failed")
logger.exception("Unhandled exception")
"""

import logging
from logging.handlers import RotatingFileHandler

from config import LOG_DIR, LOG_FILE, LOG_LEVEL

_INITIALIZED = False


def setup_logging():
    """
    Configure application logging.

    Safe to call multiple times.
    """

    global _INITIALIZED

    if _INITIALIZED:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(
        getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    )

    # Remove existing handlers if reloaded
    if root_logger.handlers:
        root_logger.handlers.clear()

    # ==========================================================
    # Console
    # ==========================================================

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)

    # ==========================================================
    # Main Log File
    # ==========================================================

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )

    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)

    # ==========================================================
    # Error Log
    # ==========================================================

    error_handler = RotatingFileHandler(
        LOG_DIR / "error.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )

    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    root_logger.addHandler(error_handler)

    _INITIALIZED = True


def get_logger(name: str) -> logging.Logger:
    """
    Return configured logger.

    Example:

        logger = get_logger(__name__)
    """

    setup_logging()

    return logging.getLogger(name)

def set_log_level(level: str):
    """
    Change logging level at runtime.
    """

    logging.getLogger().setLevel(
        getattr(logging, level.upper(), logging.INFO)
    )
