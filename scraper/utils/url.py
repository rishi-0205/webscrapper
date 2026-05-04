"""
utils/url.py

URL validation, normalization, and utility functions.
Every URL passes through here before touching anything else.

Usage:
    from scraper.utils.url import normalize_url, is_valid_url, extract_domain

    clean = normalize_url("HTTPS://Docs.Python.ORG/3/#intro")
    # → "https://docs.python.org/3/"

    valid = is_valid_url("not-a-url")
    # → False

    domain = extract_domain("https://docs.python.org/3/tutorial/")
    # → "docs.python.org"
"""

from urllib.parse import (
    urlparse,
    urlunparse,
    urljoin,
    urlencode,
    parse_qsl,
)

from scraper.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# VALIDATION
# =============================================================================

def is_valid_url(url: str) -> bool:
    """
    Check if a URL is valid and scrapeable.

    A valid URL must:
    - Be a non-empty string
    - Have a scheme (http or https)
    - Have a netloc (domain)

    Args:
        url: The URL string to validate

    Returns:
        True if valid, False otherwise
    """
    if not url or not isinstance(url, str):
        return False

    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


# =============================================================================
# NORMALIZATION
# =============================================================================

def normalize_url(url: str) -> str | None:
    """
    Normalize a URL to its canonical form.

    Applies the following transformations:
    - Strips leading/trailing whitespace
    - Lowercases the scheme and domain
    - Removes URL fragments (#section)
    - Removes empty query strings
    - Sorts query parameters for consistency
    - Ensures trailing slash on bare paths

    Args:
        url: Raw URL string to normalize

    Returns:
        Normalized URL string, or None if URL is invalid
    """
    if not is_valid_url(url):
        logger.warning(f"Cannot normalize invalid URL: '{url}'")
        return None

    try:
        parsed = urlparse(url.strip())

        # Lowercase scheme and netloc (domain is case-insensitive)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        # Keep path as-is (paths ARE case-sensitive on most servers)
        path = parsed.path

        # Ensure bare domain has a trailing slash
        # e.g. https://docs.python.org → https://docs.python.org/
        if not path:
            path = "/"

        # Sort query parameters for consistency
        # e.g. ?b=2&a=1 and ?a=1&b=2 are the same page
        query = ""
        if parsed.query:
            params = parse_qsl(parsed.query, keep_blank_values=False)
            params.sort()
            query = urlencode(params)

        # Drop fragment entirely — it's client-side only, server never sees it
        fragment = ""

        normalized = urlunparse((scheme, netloc, path, parsed.params, query, fragment))
        return normalized

    except Exception as e:
        logger.error(f"Failed to normalize URL '{url}': {e}")
        return None


# =============================================================================
# UTILITIES
# =============================================================================

def extract_domain(url: str) -> str | None:
    """
    Extract the domain (netloc) from a URL.

    Args:
        url: A valid URL string

    Returns:
        Domain string (e.g. "docs.python.org"), or None if invalid

    Example:
        extract_domain("https://docs.python.org/3/tutorial/")
        → "docs.python.org"
    """
    if not is_valid_url(url):
        return None

    return urlparse(url).netloc.lower()


def resolve_relative_url(base_url: str, relative_url: str) -> str | None:
    """
    Resolve a relative URL against a base URL.

    Handles all relative URL forms:
    - Absolute path:  /tutorial/index.html
    - Relative path:  ../glossary.html
    - Protocol-rel:   //docs.python.org/3/

    Args:
        base_url:     The page the link was found on
        relative_url: The href value from an anchor tag

    Returns:
        Fully resolved absolute URL, or None if resolution fails

    Example:
        resolve_relative_url(
            "https://docs.python.org/3/",
            "/3/tutorial/index.html"
        )
        → "https://docs.python.org/3/tutorial/index.html"
    """
    if not base_url or not relative_url:
        return None

    try:
        resolved = urljoin(base_url, relative_url.strip())
        return normalize_url(resolved)
    except Exception as e:
        logger.error(f"Failed to resolve '{relative_url}' against '{base_url}': {e}")
        return None


def is_same_domain(url1: str, url2: str) -> bool:
    """
    Check if two URLs belong to the same domain.
    Useful later in the crawler to stay within a site.

    Args:
        url1: First URL
        url2: Second URL

    Returns:
        True if both URLs share the same domain

    Example:
        is_same_domain(
            "https://docs.python.org/3/",
            "https://docs.python.org/3/tutorial/"
        )
        → True
    """
    domain1 = extract_domain(url1)
    domain2 = extract_domain(url2)

    if not domain1 or not domain2:
        return False

    return domain1 == domain2