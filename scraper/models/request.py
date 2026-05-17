"""
Defines the ScrapeRequest model — the input contract for the scraper.
Every scrape operation starts with one of these.

Usage:
    from scraper.models.request import ScrapeRequest

    # Minimal — just a URL
    request = ScrapeRequest(url="https://docs.python.org/3/")

    # Full control
    request = ScrapeRequest(
        url="https://docs.python.org/3/",
        use_browser=True,
        timeout=60,
        headers={"Accept-Language": "en-US"},
        tags=["h1", "h2", "p"]
    )
"""

from dataclasses import dataclass, field
from scraper.config.settings import (
    REQUEST_TIMEOUT,
    DEFAULT_USER_AGENT,
    CONTENT_TAGS,
)


@dataclass
class ScrapeRequest:
    """
    Represents a single scrape job — everything the scraper
    needs to know before it starts working.

    Attributes:
        url:          The page to scrape. Required, no default.
        use_browser:  If True, uses Playwright instead of requests.
                      Use for JS-rendered pages.
        timeout:      Seconds to wait for server response.
        headers:      Custom HTTP headers. Merged with defaults.
        tags:         HTML tags to extract content from.
    """

    # Required — no default, must always be provided
    url: str

    # Optional — all have sensible defaults from settings
    use_browser: bool = False
    timeout: int = REQUEST_TIMEOUT
    headers: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=lambda: CONTENT_TAGS.copy())

    # Optional proxy — e.g. "http://user:pass@proxy-host:8080"
    # Full proxy rotation system will be added in optimization phase
    proxy: str = None

    def __post_init__(self):
        """
        Runs automatically after __init__.
        Validates and cleans the request before it goes anywhere.
        """
        self._validate()
        self._normalize()

    def _validate(self) -> None:
        """Raise clear errors early rather than failing deep in the stack."""
        if not self.url:
            raise ValueError("ScrapeRequest requires a non-empty URL.")

        if not self.url.startswith(("http://", "https://")):
            raise ValueError(
                f"Invalid URL '{self.url}'. Must start with http:// or https://"
            )

        if self.timeout <= 0:
            raise ValueError(
                f"Timeout must be a positive integer, got {self.timeout}."
            )

    def _normalize(self) -> None:
        """Clean and normalize values for consistency."""
        # Strip whitespace from URL
        self.url = self.url.strip()

        # Remove URL fragment (e.g. https://example.com/page#section -> no #section)
        # Fragments are client-side only — the server never sees them
        if "#" in self.url:
            self.url = self.url.split("#")[0]