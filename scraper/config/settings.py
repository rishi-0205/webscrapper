"""
config/settings.py

Central configuration for the scraper.
All constants, paths, and default values live here.
No other file should hardcode these values.
"""

from pathlib import Path

# =============================================================================
# PATHS
# =============================================================================

# Root of the entire project (webscrapper/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Where scraped results are saved
OUTPUT_DIR = BASE_DIR / "output"

# Where log files are saved
LOG_DIR = BASE_DIR / "logs"

# Ensure these directories always exist when settings are imported
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# HTTP / FETCHER SETTINGS
# =============================================================================

# How long to wait for a server response before giving up (seconds)
REQUEST_TIMEOUT = 30

# How many times to retry a failed request before marking it as failed
MAX_RETRIES = 3

# How long to wait between retries (seconds)
RETRY_DELAY = 2

# Default User-Agent header — mimics a real Chrome browser
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)


# =============================================================================
# PLAYWRIGHT SETTINGS
# =============================================================================

# Run browser in headless mode (no visible window)
# Set to False if you want to watch the browser during development
PLAYWRIGHT_HEADLESS = True

# How long Playwright waits for a page to fully load (milliseconds)
PLAYWRIGHT_TIMEOUT = 30000


# =============================================================================
# PARSER SETTINGS
# =============================================================================

# HTML tags the parser will extract text content from
CONTENT_TAGS = ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "code", "pre"]

# HTML tags to strip out completely before parsing (noise)
NOISE_TAGS = ["script", "style", "nav", "footer", "header", "aside", "form"]


# =============================================================================
# LOGGING SETTINGS
# =============================================================================

# Log level — controls what gets printed/saved
# Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = "DEBUG"

# Name of the log file inside logs/
LOG_FILE = "scraper.log"

# Full path to the log file
LOG_FILE_PATH = LOG_DIR / LOG_FILE