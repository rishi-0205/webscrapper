"""
Entry point for the scraper.
Wires together Scraper, Storage, and CLI argument handling.

Usage:
    # Scrape the default URL (set below)
    python main.py

    # Scrape a specific URL
    python main.py https://docs.python.org/3/

    # Scrape with browser (for JS-rendered pages)
    python main.py https://example.com --browser

    # Scrape without saving to file
    python main.py https://docs.python.org/3/ --no-save
"""

import argparse
import sys

from scraper.core.scraper import Scraper
from scraper.models.request import ScrapeRequest
from scraper.storage.json_storage import JsonStorage
from scraper.utils.logger import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# DEFAULT URL — change this during development to whatever you're testing
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_URL = "https://docs.python.org/3/"


# =============================================================================
# CLI
# =============================================================================

def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        prog="webscraper",
        description="Scrape a webpage and extract clean structured content.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py
  python main.py https://docs.python.org/3/
  python main.py https://example.com --browser
  python main.py https://docs.python.org/3/ --no-save
        """,
    )

    parser.add_argument(
        "url",
        nargs="?",                          # Optional — falls back to DEFAULT_URL
        default=DEFAULT_URL,
        help=f"URL to scrape (default: {DEFAULT_URL})",
    )

    parser.add_argument(
        "--browser",
        action="store_true",
        default=False,
        help="Force Playwright browser for JS-rendered pages",
    )

    parser.add_argument(
        "--no-save",
        action="store_true",
        default=False,
        help="Print result to console without saving to file",
    )

    parser.add_argument(
        "--proxy",
        default=None,
        help='Optional proxy URL (e.g. "http://user:pass@host:port")',
    )

    return parser.parse_args()


# =============================================================================
# CORE RUN LOGIC
# =============================================================================

def run(url: str, use_browser: bool, save: bool, proxy: str = None) -> int:
    """
    Execute the full scrape pipeline.

    Args:
        url:         URL to scrape
        use_browser: Whether to force Playwright
        save:        Whether to persist result to JSON
        proxy:       Optional proxy URL string

    Returns:
        Exit code — 0 for success, 1 for failure
    """
    # Build the request
    request = ScrapeRequest(
        url=url,
        use_browser=use_browser,
        proxy=proxy,
    )

    # Run the scraper
    with Scraper() as scraper:
        response = scraper.scrape(request)

    # Handle failure
    if not response.success:
        logger.error(f"Scrape failed: {response.error}")
        print(f"\n❌ Scrape failed: {response.error}")
        return 1

    # Print result summary to console
    _print_result(response)

    # Save to storage if requested
    if save:
        storage = JsonStorage()

        if storage.save(response):
            print(f"\n💾 Saved to: output/")
        else:
            print(f"\n⚠️  Result not saved due to storage error.")
            return 1

    return 0


# =============================================================================
# OUTPUT FORMATTING
# =============================================================================

def _print_result(response) -> None:
    """
    Print a clean, readable summary of the scrape result to console.

    Args:
        response: A successful ScrapeResponse
    """
    divider = "─" * 60

    print(f"\n{divider}")
    print(f"  ✅ SCRAPE SUCCESSFUL")
    print(f"{divider}")
    print(f"  URL          : {response.url}")
    print(f"  Status       : {response.status_code}")
    print(f"  Title        : {response.title or '(none)'}")
    print(f"  Content      : {len(response.content)} characters")
    print(f"  Links found  : {len(response.links)}")
    print(f"  Browser used : {'Yes' if response.used_browser else 'No'}")
    print(f"  Scraped at   : {response.scraped_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{divider}")

    # Preview first 500 chars of content
    if response.content:
        preview = response.content[:500]
        if len(response.content) > 500:
            preview += "..."
        print(f"\n📄 Content Preview:\n\n{preview}\n")

    # Preview first 5 links
    if response.links:
        print(f"🔗 First 5 Links:")
        for link in response.links[:5]:
            print(f"   {link}")
        if len(response.links) > 5:
            print(f"   ... and {len(response.links) - 5} more")
        print()


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    args = parse_args()

    exit_code = run(
        url=args.url,
        use_browser=args.browser,
        save=not args.no_save,
        proxy=args.proxy,
    )

    sys.exit(exit_code)