"""
utils/headers.py

Generates realistic browser-like HTTP headers for scraper requests.
Without proper headers, many websites detect and block automated requests.

Usage:
    from scraper.utils.headers import get_default_headers, get_headers_for_url

    # Get a basic set of browser-like headers
    headers = get_default_headers()

    # Get headers tailored to a specific URL (sets correct Referer & Origin)
    headers = get_headers_for_url("https://docs.python.org/3/")
"""

import random
from urllib.parse import urlparse

from scraper.config.settings import DEFAULT_USER_AGENT


# =============================================================================
# USER AGENT POOL
# =============================================================================

# A pool of real, current browser User-Agent strings.
# Rotating these makes requests look more like real users.
USER_AGENTS = [
    # Chrome on Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    # Chrome on macOS
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    # Firefox on Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) "
        "Gecko/20100101 Firefox/124.0"
    ),
    # Firefox on macOS
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:124.0) "
        "Gecko/20100101 Firefox/124.0"
    ),
    # Safari on macOS
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.4.1 Safari/605.1.15"
    ),
    # Edge on Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0"
    ),
]


# =============================================================================
# HEADER BUILDERS
# =============================================================================

def get_default_headers(randomize_user_agent: bool = True) -> dict:
    """
    Returns a complete set of browser-like HTTP headers.

    These headers mimic what a real Chrome browser sends,
    making requests appear legitimate to most websites.

    Args:
        randomize_user_agent: If True, picks a random UA from the pool.
                              If False, uses DEFAULT_USER_AGENT from settings.

    Returns:
        Dictionary of HTTP headers
    """
    user_agent = (
        random.choice(USER_AGENTS)
        if randomize_user_agent
        else DEFAULT_USER_AGENT
    )

    return {
        "User-Agent": user_agent,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }


def get_headers_for_url(url: str, randomize_user_agent: bool = True) -> dict:
    """
    Returns browser-like headers tailored to a specific URL.

    Adds the correct Origin and Referer headers based on the URL,
    which makes requests look even more like they came from a real browser
    navigating to the page naturally.

    Args:
        url:                  The URL being requested
        randomize_user_agent: Whether to rotate the User-Agent

    Returns:
        Dictionary of HTTP headers with URL-specific values

    Example:
        get_headers_for_url("https://docs.python.org/3/tutorial/")
        → headers with Origin: "https://docs.python.org"
                      Referer: "https://docs.python.org/"
    """
    headers = get_default_headers(randomize_user_agent)

    try:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        headers["Origin"] = origin
        headers["Referer"] = f"{origin}/"
        headers["Host"] = parsed.netloc

    except Exception:
        # If URL parsing fails, return headers without Origin/Referer
        # Better to send incomplete headers than crash
        pass

    return headers


def merge_headers(base: dict, custom: dict) -> dict:
    """
    Merge custom headers into base headers.
    Custom headers take priority over base headers.

    Used when a ScrapeRequest provides its own headers —
    they override defaults without discarding them entirely.

    Args:
        base:   Default browser-like headers
        custom: User-provided headers from ScrapeRequest

    Returns:
        Merged header dictionary

    Example:
        merge_headers(
            base=get_default_headers(),
            custom={"Authorization": "Bearer token123"}
        )
    """
    return {**base, **custom}