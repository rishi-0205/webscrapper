"""
Centralized logger for the entire scraper project.
Every module imports get_logger() from here instead of
configuring their own logging setup.

Usage:
    from scraper.utils.logger import get_logger
    logger = get_logger(__name__)

    logger.debug("Detailed debug info")
    logger.info("General information")
    logger.warning("Something unexpected but not breaking")
    logger.error("Something failed")
    logger.critical("Something catastrophically failed")
"""

import logging
import sys
from pathlib import Path

from scraper.config.settings import LOG_FILE_PATH, LOG_LEVEL


# =============================================================================
# FORMATTERS
# =============================================================================

# Console formatter — clean and readable for human eyes
CONSOLE_FORMAT = (
    "[%(asctime)s] "        # Timestamp
    "%(levelname)-8s "      # Log level, padded to 8 chars (e.g. "INFO    ")
    "%(name)s: "            # Module name (e.g. "scraper.core.fetcher")
    "%(message)s"           # The actual log message
)

# File formatter — more detailed for debugging later
FILE_FORMAT = (
    "[%(asctime)s] "
    "%(levelname)-8s "
    "%(name)s "
    "[%(filename)s:%(lineno)d]: "   # Exact file and line number
    "%(message)s"
)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# =============================================================================
# INTERNAL SETUP — runs once when this module is first imported
# =============================================================================

def _setup_root_logger() -> None:
    """
    Configure the root logger once for the entire application.
    All child loggers created via get_logger() inherit this setup.
    Called automatically when this module is imported.
    """
    root_logger = logging.getLogger("scraper")

    # Avoid adding duplicate handlers if this is called multiple times
    if root_logger.handlers:
        return

    root_logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.DEBUG))

    # --- Console Handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(
        logging.Formatter(fmt=CONSOLE_FORMAT, datefmt=DATE_FORMAT)
    )

    # --- File Handler ---
    file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(fmt=FILE_FORMAT, datefmt=DATE_FORMAT)
    )

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


# Run setup immediately on import
_setup_root_logger()


# =============================================================================
# PUBLIC API
# =============================================================================

def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger for a module.

    Always pass __name__ so the logger identifies itself
    by its module path (e.g. scraper.core.fetcher).

    Args:
        name: The module name, always pass __name__

    Returns:
        A configured Logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Scraper started")
    """
    return logging.getLogger(name)