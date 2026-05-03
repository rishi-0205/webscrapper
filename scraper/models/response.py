"""
models/response.py

Defines the ScrapeResponse model — the output contract for the scraper.
Every scrape operation returns one of these, whether it succeeded or failed.

Usage:
    from scraper.models.response import ScrapeResponse

    # A successful response
    response = ScrapeResponse(
        url="https://docs.python.org/3/",
        status_code=200,
        title="Python 3 Documentation",
        content="Welcome to Python 3...",
        links=["https://docs.python.org/3/tutorial/"],
        success=True,
    )

    # A failed response
    response = ScrapeResponse(
        url="https://docs.python.org/3/",
        status_code=500,
        success=False,
        error="Connection timed out after 30s"
    )
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ScrapeResponse:
    """
    Represents the result of a single scrape operation.
    Always returned by the scraper — even on failure.

    Checking success before using data is always the right pattern:
        if response.success:
            print(response.title)
        else:
            print(response.error)

    Attributes:
        url:          The URL that was scraped.
        status_code:  HTTP status code (200, 404, 500, etc). -1 if request never completed.
        title:        Page <title> tag content.
        content:      Extracted text content from the page.
        links:        All anchor href links found on the page.
        success:      True if scrape completed without error.
        error:        Error message if success is False, None otherwise.
        scraped_at:   UTC timestamp of when the scrape completed.
        used_browser: Whether Playwright was used instead of requests.
    """

    # Core identity
    url: str
    status_code: int = -1

    # Extracted content
    title: str = ""
    content: str = ""
    links: list[str] = field(default_factory=list)

    # Status
    success: bool = False
    error: str = None

    # Metadata
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    used_browser: bool = False

    def to_dict(self) -> dict:
        """
        Serialize to a plain dictionary for storage or logging.
        Converts datetime to ISO 8601 string for JSON compatibility.

        Returns:
            dict representation of this response
        """
        return {
            "url": self.url,
            "status_code": self.status_code,
            "title": self.title,
            "content": self.content,
            "links": self.links,
            "success": self.success,
            "error": self.error,
            "scraped_at": self.scraped_at.isoformat(),
            "used_browser": self.used_browser,
        }

    def summary(self) -> str:
        """
        Returns a short human-readable summary of the response.
        Useful for logging and debugging.

        Returns:
            Single line summary string
        """
        if self.success:
            return (
                f"[SUCCESS] {self.url} | "
                f"Status: {self.status_code} | "
                f"Title: '{self.title}' | "
                f"Content: {len(self.content)} chars | "
                f"Links: {len(self.links)}"
            )
        return (
            f"[FAILED] {self.url} | "
            f"Status: {self.status_code} | "
            f"Error: {self.error}"
        )