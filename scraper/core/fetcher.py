"""
Handles all HTTP communication for the scraper.
Responsible for fetching raw HTML from URLs using either:
  - requests       → fast, lightweight, for static pages
  - Playwright     → full browser, for JS-rendered pages

This module knows nothing about parsing or storage.
It only fetches and returns raw HTML + metadata.

Usage:
    from scraper.core.fetcher import Fetcher
    from scraper.models.request import ScrapeRequest
    from scraper.models.response import ScrapeResponse

    fetcher = Fetcher()
    response = fetcher.fetch(ScrapeRequest(url="https://docs.python.org/3/"))

    if response.success:
        print(response.raw_html)
"""

import time

import requests
from requests.exceptions import (
    ConnectionError,
    Timeout,
    TooManyRedirects,
    HTTPError,
)

from scraper.config.settings import (
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY,
    PLAYWRIGHT_HEADLESS,
    PLAYWRIGHT_TIMEOUT,
)
from scraper.models.request import ScrapeRequest
from scraper.models.response import ScrapeResponse
from scraper.utils.headers import get_headers_for_url, merge_headers
from scraper.utils.logger import get_logger

logger = get_logger(__name__)


class Fetcher:
    """
    Fetches raw HTML from a URL using either requests or Playwright.

    Handles:
    - Retry logic with exponential backoff
    - Browser-like headers
    - Optional proxy support
    - Static (requests) and dynamic (Playwright) fetching
    - All network error cases gracefully

    Example:
        fetcher = Fetcher()
        response = fetcher.fetch(ScrapeRequest(url="https://example.com"))
    """

    def __init__(self, session: requests.Session = None):
        """
        Initialize the Fetcher with an optional shared session.

        Using a shared session is more efficient than creating a new
        connection for every request — it reuses TCP connections (keep-alive).

        Args:
            session: Optional pre-configured requests.Session.
                     If not provided, a new session is created.
        """
        self.session = session or self._create_session()

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def fetch(self, request: ScrapeRequest) -> ScrapeResponse:
        """
        Fetch a page and return raw HTML wrapped in a ScrapeResponse.

        Automatically chooses between static (requests) and dynamic
        (Playwright) fetching based on request.use_browser.

        Args:
            request: A ScrapeRequest describing what to fetch

        Returns:
            ScrapeResponse with raw_html populated on success,
            or success=False and error message on failure
        """
        logger.info(f"Fetching: {request.url}")

        if request.use_browser:
            return self._fetch_with_playwright(request)
        return self._fetch_with_requests(request)

    def close(self) -> None:
        """
        Close the underlying requests session.
        Call this when the fetcher is no longer needed.
        """
        if self.session:
            self.session.close()
            logger.debug("Fetcher session closed.")

    # =========================================================================
    # STATIC FETCHING — requests
    # =========================================================================

    def _fetch_with_requests(self, request: ScrapeRequest) -> ScrapeResponse:
        """
        Fetch a static page using the requests library.
        Retries up to MAX_RETRIES times with exponential backoff.

        Args:
            request: The ScrapeRequest to process

        Returns:
            ScrapeResponse with raw HTML or error details
        """
        headers = merge_headers(
            get_headers_for_url(request.url),
            request.headers,
        )
        proxies = {"http": request.proxy, "https": request.proxy} if request.proxy else None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.debug(f"Attempt {attempt}/{MAX_RETRIES} → {request.url}")

                response = self.session.get(
                    url=request.url,
                    headers=headers,
                    timeout=request.timeout,
                    proxies=proxies,
                    allow_redirects=True,
                )

                # Raise an exception for 4xx and 5xx status codes
                response.raise_for_status()

                logger.info(
                    f"Success [{response.status_code}] → {request.url} "
                    f"({len(response.text)} chars)"
                )

                return ScrapeResponse(
                    url=request.url,
                    status_code=response.status_code,
                    raw_html=response.text,
                    success=True,
                    used_browser=False,
                )

            except HTTPError as e:
                status_code = e.response.status_code if e.response else -1
                error = f"HTTP {status_code} error: {e}"

                # Do not retry client errors (4xx) — they won't resolve on retry
                # Only retry server errors (5xx)
                if status_code and 400 <= status_code < 500:
                    logger.warning(f"Client error, will not retry: {error}")
                    return ScrapeResponse(
                        url=request.url,
                        status_code=status_code,
                        success=False,
                        error=error,
                    )

                logger.warning(f"Server error on attempt {attempt}: {error}")

            except Timeout:
                error = f"Request timed out after {request.timeout}s"
                logger.warning(f"Timeout on attempt {attempt}: {error}")

            except TooManyRedirects:
                error = "Too many redirects — possible redirect loop"
                logger.warning(f"{error} → {request.url}")
                # No point retrying a redirect loop
                return ScrapeResponse(
                    url=request.url,
                    status_code=-1,
                    success=False,
                    error=error,
                )

            except ConnectionError:
                error = "Connection failed — check network or URL"
                logger.warning(f"Connection error on attempt {attempt}: {error}")

            except Exception as e:
                error = f"Unexpected error: {type(e).__name__}: {e}"
                logger.error(f"Unexpected error on attempt {attempt}: {error}")

            # Exponential backoff before next retry
            # attempt=1 → wait 2s, attempt=2 → wait 4s, attempt=3 → wait 8s
            if attempt < MAX_RETRIES:
                wait = RETRY_DELAY * (2 ** (attempt - 1))
                logger.debug(f"Waiting {wait}s before retry...")
                time.sleep(wait)

        # All retries exhausted
        final_error = f"Failed after {MAX_RETRIES} attempts: {error}"
        logger.error(final_error)
        return ScrapeResponse(
            url=request.url,
            status_code=-1,
            success=False,
            error=final_error,
        )

    # =========================================================================
    # DYNAMIC FETCHING — Playwright
    # =========================================================================

    def _fetch_with_playwright(self, request: ScrapeRequest) -> ScrapeResponse:
        """
        Fetch a JS-rendered page using Playwright (headless Chromium).

        Used when request.use_browser=True. Playwright spins up a real
        browser, navigates to the URL, waits for JS to execute, and
        returns the fully rendered HTML.

        Args:
            request: The ScrapeRequest to process

        Returns:
            ScrapeResponse with fully rendered HTML or error details
        """
        # Import here so Playwright is only loaded when actually needed
        # This keeps startup fast for static-only scraping
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
        except ImportError:
            error = "Playwright not installed. Run: pip install playwright && playwright install chromium"
            logger.error(error)
            return ScrapeResponse(
                url=request.url,
                status_code=-1,
                success=False,
                error=error,
            )

        logger.debug(f"Launching Playwright browser for: {request.url}")

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
                context = browser.new_context(
                    user_agent=merge_headers(
                        get_headers_for_url(request.url),
                        request.headers,
                    ).get("User-Agent"),
                    proxy={"server": request.proxy} if request.proxy else None,
                )
                page = context.new_page()

                # Navigate and wait until network is idle
                # "networkidle" means no network requests for 500ms — page is fully loaded
                response = page.goto(
                    request.url,
                    timeout=PLAYWRIGHT_TIMEOUT,
                    wait_until="networkidle",
                )

                status_code = response.status if response else -1
                html = page.content()

                browser.close()

                logger.info(
                    f"Playwright success [{status_code}] → {request.url} "
                    f"({len(html)} chars)"
                )

                return ScrapeResponse(
                    url=request.url,
                    status_code=status_code,
                    raw_html=html,
                    success=True,
                    used_browser=True,
                )

        except PlaywrightTimeout:
            error = f"Playwright timed out after {PLAYWRIGHT_TIMEOUT}ms"
            logger.error(f"{error} → {request.url}")
            return ScrapeResponse(
                url=request.url,
                status_code=-1,
                success=False,
                error=error,
                used_browser=True,
            )

        except Exception as e:
            error = f"Playwright error: {type(e).__name__}: {e}"
            logger.error(f"{error} → {request.url}")
            return ScrapeResponse(
                url=request.url,
                status_code=-1,
                success=False,
                error=error,
                used_browser=True,
            )

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    def _create_session(self) -> requests.Session:
        """
        Create and configure a reusable requests Session.

        A Session persists TCP connections across requests (keep-alive),
        which is significantly faster than creating a new connection each time.

        Returns:
            Configured requests.Session instance
        """
        session = requests.Session()

        # Mount retry-capable adapters for both http and https
        # This handles connection-level retries at the transport layer
        adapter = requests.adapters.HTTPAdapter(
            max_retries=0,  # We handle retries manually for full control
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        logger.debug("Requests session created.")
        return session
