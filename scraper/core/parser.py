"""
core/parser.py

Parses raw HTML and extracts clean, structured content.
Receives raw_html from the fetcher via ScrapeResponse and
populates title, content, and links on that same response.

This module knows nothing about HTTP, fetching, or storage.
It only transforms raw HTML into structured data.

Usage:
    from scraper.core.parser import Parser
    from scraper.models.response import ScrapeResponse

    parser = Parser()
    response = parser.parse(response)   # mutates and returns response

    print(response.title)
    print(response.content)
    print(response.links)
"""

import re
import unicodedata

from bs4 import BeautifulSoup

from scraper.config.settings import CONTENT_TAGS, NOISE_TAGS
from scraper.models.response import ScrapeResponse
from scraper.utils.logger import get_logger
from scraper.utils.url import resolve_relative_url, is_valid_url

logger = get_logger(__name__)


class Parser:
    """
    Parses raw HTML into structured, clean content.

    Takes a ScrapeResponse with raw_html populated (by Fetcher)
    and fills in title, content, and links.

    All parsing steps are isolated into private methods so each
    concern is testable and replaceable independently.

    Example:
        parser = Parser()
        response = parser.parse(response)
    """

    def __init__(
        self,
        content_tags: list[str] = None,
        noise_tags: list[str] = None,
    ):
        """
        Initialize the Parser with configurable tag lists.

        Args:
            content_tags: HTML tags to extract text from.
                          Defaults to settings.CONTENT_TAGS.
            noise_tags:   HTML tags to strip before parsing.
                          Defaults to settings.NOISE_TAGS.
        """
        self.content_tags = content_tags or CONTENT_TAGS
        self.noise_tags = noise_tags or NOISE_TAGS

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def parse(self, response: ScrapeResponse) -> ScrapeResponse:
        """
        Parse raw HTML from a ScrapeResponse and populate its fields.

        Mutates and returns the same response object — does not create
        a new one. If raw_html is empty or parsing fails, the response
        is returned with empty fields and success=False.

        Args:
            response: A ScrapeResponse with raw_html populated by Fetcher

        Returns:
            The same ScrapeResponse with title, content, links populated
        """
        if not response.raw_html:
            logger.warning(f"No HTML to parse for: {response.url}")
            response.success = False
            response.error = "No HTML content received from fetcher"
            return response

        logger.info(f"Parsing: {response.url}")

        try:
            # Parse raw HTML into a BeautifulSoup tree using lxml engine
            soup = BeautifulSoup(response.raw_html, "lxml")

            # Step 1 — Remove all noise before doing anything else
            self._remove_noise(soup)

            # Step 2 — Extract title
            response.title = self._extract_title(soup)

            # Step 3 — Extract main text content
            response.content = self._extract_content(soup)

            # Step 4 — Extract and resolve all links
            response.links = self._extract_links(soup, base_url=response.url)

            logger.info(
                f"Parsed: '{response.title}' | "
                f"{len(response.content)} chars | "
                f"{len(response.links)} links"
            )

        except Exception as e:
            error = f"Parsing failed: {type(e).__name__}: {e}"
            logger.error(f"{error} → {response.url}")
            response.success = False
            response.error = error

        return response

    # =========================================================================
    # STEP 1 — NOISE REMOVAL
    # =========================================================================

    def _remove_noise(self, soup: BeautifulSoup) -> None:
        """
        Remove all noise tags from the soup tree in-place.

        Noise tags are elements that never contain meaningful content:
        scripts, styles, navbars, footers, sidebars, forms, etc.

        Removing these before extraction ensures clean output with
        no javascript, CSS, or navigation text bleeding into content.

        Args:
            soup: BeautifulSoup tree — modified in place
        """
        removed = 0
        for tag in self.noise_tags:
            for element in soup.find_all(tag):
                element.decompose()     # decompose() removes element AND frees memory
                removed += 1

        logger.debug(f"Removed {removed} noise elements")

    # =========================================================================
    # STEP 2 — TITLE EXTRACTION
    # =========================================================================

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """
        Extract the page title with multiple fallback strategies.

        Tries in order:
        1. <title> tag                    → most reliable
        2. <h1> tag                       → main heading if no title
        3. First <h2> tag                 → fallback heading
        4. Empty string                   → last resort

        Args:
            soup: Cleaned BeautifulSoup tree (noise already removed)

        Returns:
            Page title string, or empty string if none found
        """
        # Strategy 1 — <title> tag
        title_tag = soup.find("title")
        if title_tag and title_tag.get_text(strip=True):
            return self._clean_text(title_tag.get_text())

        # Strategy 2 — <h1> tag
        h1_tag = soup.find("h1")
        if h1_tag and h1_tag.get_text(strip=True):
            logger.debug("No <title> found, using <h1> as title")
            return self._clean_text(h1_tag.get_text())

        # Strategy 3 — <h2> tag
        h2_tag = soup.find("h2")
        if h2_tag and h2_tag.get_text(strip=True):
            logger.debug("No <h1> found, using <h2> as title")
            return self._clean_text(h2_tag.get_text())

        logger.warning("Could not extract any title from page")
        return ""

    # =========================================================================
    # STEP 3 — CONTENT EXTRACTION
    # =========================================================================

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """
        Extract meaningful text content from the page.

        Finds all elements matching content_tags (h1-h6, p, li, code, pre)
        and joins their text into a single clean string.

        Preserves document order — content appears in the same order
        as it does on the original page.

        Args:
            soup: Cleaned BeautifulSoup tree (noise already removed)

        Returns:
            Extracted text content as a single string
        """
        content_parts = []

        for element in soup.find_all(self.content_tags):
            text = element.get_text(separator=" ", strip=True)
            cleaned = self._clean_text(text)

            if cleaned:
                content_parts.append(cleaned)

        content = "\n".join(content_parts)
        logger.debug(f"Extracted {len(content_parts)} content blocks")
        return content

    # =========================================================================
    # STEP 4 — LINK EXTRACTION
    # =========================================================================

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """
        Extract all hyperlinks from the page.

        Finds every <a href="..."> tag and:
        1. Skips empty, anchor-only (#), mailto:, tel:, javascript: hrefs
        2. Resolves relative URLs to absolute using base_url
        3. Validates the resolved URL
        4. Deduplicates the final list

        Args:
            soup:     Cleaned BeautifulSoup tree
            base_url: The page URL — used to resolve relative links

        Returns:
            Deduplicated list of valid absolute URLs found on the page
        """
        seen = set()
        links = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()

            # Skip empty, fragment-only, and non-http schemes
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue

            # Resolve relative URLs to absolute
            absolute_url = resolve_relative_url(base_url, href)

            if not absolute_url or not is_valid_url(absolute_url):
                continue

            # Deduplicate
            if absolute_url not in seen:
                seen.add(absolute_url)
                links.append(absolute_url)

        logger.debug(f"Extracted {len(links)} unique links")
        return links

    # =========================================================================
    # TEXT CLEANING
    # =========================================================================

    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize a raw text string.

        Applies the following transformations:
        1. Normalize unicode characters (e.g. fancy quotes → standard)
        2. Replace non-breaking spaces with regular spaces
        3. Collapse multiple whitespace/newlines into single spaces
        4. Strip leading and trailing whitespace

        Args:
            text: Raw text string extracted from HTML

        Returns:
            Cleaned, normalized text string
        """
        if not text:
            return ""

        # Normalize unicode — converts fancy characters to ASCII equivalents
        # NFKC normalization handles ligatures, special spaces, etc.
        text = unicodedata.normalize("NFKC", text)

        # Replace non-breaking spaces (\xa0) with regular spaces
        text = text.replace("\xa0", " ")

        # Collapse multiple whitespace characters into a single space
        text = re.sub(r"[ \t]+", " ", text)

        # Collapse multiple newlines into a single newline
        text = re.sub(r"\n{2,}", "\n", text)

        # Final strip
        return text.strip()