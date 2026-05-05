"""
core/scraper.py

Orchestrates the full scrape pipeline:
    ScrapeRequest → Fetcher → Parser → ScrapeResponse

This is the only file that knows both Fetcher and Parser exist.
All external code interacts with this class only — never with
Fetcher or Parser directly.

Usage:
    # Basic usage
    from scraper.core.scraper import Scraper
    from scraper.models.request import ScrapeRequest

    scraper = Scraper()
    response = scraper.scrape(ScrapeRequest(url="https://docs.python.org/3/"))
    print(response.summary())

    # Recommended — context manager handles cleanup automatically
    with Scraper() as scraper:
        response = scraper.scrape(ScrapeRequest(url="https://docs.python.org/3/"))
        print(response.title)
"""

import time

from scraper.core.fetcher import Fetcher
from scraper.core.parser import Parser
from scraper.models.request import ScrapeRequest
from scraper.models.response import ScrapeResponse
from scraper.utils.logger import get_logger

logger = get_logger(__name__)

# Minimum number of characters a static fetch must return
# before we consider it a JS-rendered page and retry with Playwright.
# A page with fewer characters than this is likely an empty shell.
MIN_CONTENT_LENGTH = 200


class Scraper:
    """
    Orchestrates the complete scrape pipeline.

    Ties together Fetcher and Parser into a single clean interface.
    Handles auto-detection of JS-rendered pages, timing, and cleanup.

    Supports both direct usage and context manager pattern:

        # Direct usage — you must call close() manually
        scraper = Scraper()
        response = scraper.scrape(request)
        scraper.close()

        # Context manager — cleanup is automatic (recommended)
        with Scraper() as scraper:
            response = scraper.scrape(request)

    Args:
        fetcher:      Optional pre-configured Fetcher instance.
                      If not provided, a default Fetcher is created.
        parser:       Optional pre-configured Parser instance.
                      If not provided, a default Parser is created.
        auto_browser: If True, automatically retries with Playwright
                      when static fetch returns too little content.
                      Default: True
    """

    def __init__(
        self,
        fetcher: Fetcher = None,
        parser: Parser = None,
        auto_browser: bool = True,
    ):
        self.fetcher = fetcher or Fetcher()
        self.parser = parser or Parser()
        self.auto_browser = auto_browser

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def scrape(self, request: ScrapeRequest) -> ScrapeResponse:
        """
        Execute the full scrape pipeline for a single URL.

        Pipeline:
            1. Fetch raw HTML (static or browser-based)
            2. Auto-detect JS rendering if needed
            3. Parse HTML into structured content
            4. Return populated ScrapeResponse

        Args:
            request: ScrapeRequest defining what to scrape

        Returns:
            ScrapeResponse with title, content, links populated on success,
            or success=False with error message on failure.
        """
        logger.info(f"Starting scrape → {request.url}")
        start_time = time.time()

        # ── Step 1: Fetch ─────────────────────────────────────────────────────
        response = self.fetcher.fetch(request)

        if not response.success:
            logger.error(f"Fetch failed → {response.summary()}")
            return response

        # ── Step 2: Auto-detect JS rendering ─────────────────────────────────
        # If static fetch returned very little content and the request
        # didn't explicitly ask for a browser, try again with Playwright.
        # This handles pages that look like:
        #   <html><body><div id="app"></div></body></html>  ← JS shell
        if (
            self.auto_browser
            and not request.use_browser
            and self._looks_js_rendered(response)
        ):
            logger.info(
                f"Content too sparse ({len(response.raw_html)} chars) — "
                f"retrying with Playwright: {request.url}"
            )
            browser_request = self._make_browser_request(request)
            browser_response = self.fetcher.fetch(browser_request)

            if browser_response.success:
                response = browser_response
            else:
                logger.warning(
                    f"Playwright fallback also failed — "
                    f"proceeding with original static response"
                )

        # ── Step 3: Parse ─────────────────────────────────────────────────────
        response = self.parser.parse(response)

        # ── Step 4: Final check & timing ──────────────────────────────────────
        elapsed = round(time.time() - start_time, 2)

        if response.success and not response.content:
            # Fetch succeeded but parser got nothing — page might be
            # structured in a way our content tags don't cover
            logger.warning(
                f"Parse returned no content for: {request.url}. "
                f"Consider adding custom tags to ScrapeRequest."
            )

        logger.info(f"Scrape complete in {elapsed}s → {response.summary()}")
        return response

    def close(self) -> None:
        """
        Release all resources held by the scraper.
        Call this when done scraping — or use context manager instead.
        """
        self.fetcher.close()
        logger.debug("Scraper closed.")

    # =========================================================================
    # CONTEXT MANAGER SUPPORT
    # =========================================================================

    def __enter__(self) -> "Scraper":
        """Called when entering a `with Scraper() as scraper:` block."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Called when exiting a `with` block — even if an exception occurred.
        Ensures resources are always cleaned up.
        """
        self.close()
        # Return False so exceptions propagate normally
        return False

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    def _looks_js_rendered(self, response: ScrapeResponse) -> bool:
        """
        Heuristic check — does this response look like a JS-rendered shell?

        A page is considered JS-rendered if its raw HTML is suspiciously
        short — meaning the server sent a skeleton that JS was supposed
        to fill in, but we fetched it without running JS.

        Args:
            response: A successful ScrapeResponse from static fetch

        Returns:
            True if the page likely needs a browser to render properly
        """
        return len(response.raw_html.strip()) < MIN_CONTENT_LENGTH

    def _make_browser_request(self, original: ScrapeRequest) -> ScrapeRequest:
        """
        Create a copy of the original request with use_browser=True.

        We never mutate the original request — we create a new one.
        This keeps the original request object unchanged for the caller.

        Args:
            original: The original ScrapeRequest

        Returns:
            New ScrapeRequest identical to original but with use_browser=True
        """
        return ScrapeRequest(
            url=original.url,
            use_browser=True,
            timeout=original.timeout,
            headers=original.headers,
            tags=original.tags,
            proxy=original.proxy,
        )