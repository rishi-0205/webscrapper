"""
Unit tests for scraper/core/fetcher.py

Tests cover:
- Successful static fetch
- HTTP error handling (404, 500)
- Timeout handling
- Connection error handling
- Retry logic with exponential backoff
- No retry on 4xx client errors
- Proxy passing
"""

import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from requests.exceptions import ConnectionError, Timeout, HTTPError

from scraper.core.fetcher import Fetcher
from scraper.models.request import ScrapeRequest
from scraper.models.response import ScrapeResponse


class TestFetcherStaticFetch(unittest.TestCase):
    """Tests for _fetch_with_requests (static fetching via requests)."""

    def setUp(self):
        """Create a fresh Fetcher before each test."""
        self.fetcher = Fetcher()
        self.request = ScrapeRequest(url="https://docs.python.org/3/")

    def tearDown(self):
        """Close the fetcher session after each test."""
        self.fetcher.close()

    @patch("scraper.core.fetcher.requests.Session.get")
    def test_successful_fetch_returns_success_response(self, mock_get):
        """A 200 response should return a ScrapeResponse with success=True."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><title>Python Docs</title></html>"
        mock_response.raise_for_status = MagicMock()     # Does nothing = no error
        mock_get.return_value = mock_response

        # Act
        response = self.fetcher.fetch(self.request)

        # Assert
        self.assertTrue(response.success)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.raw_html, "<html><title>Python Docs</title></html>")
        self.assertFalse(response.used_browser)

    @patch("scraper.core.fetcher.requests.Session.get")
    def test_404_returns_failure_without_retry(self, mock_get):
        """A 404 client error should fail immediately without retrying."""
        # Arrange
        http_error = HTTPError()
        mock_http_response = MagicMock()
        mock_http_response.status_code = 404
        http_error.response = mock_http_response

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = http_error
        mock_get.return_value = mock_response

        # Act
        response = self.fetcher.fetch(self.request)

        # Assert
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 404)
        # Should only have been called once — no retries on 4xx
        mock_get.assert_called_once()

    @patch("scraper.core.fetcher.time.sleep")          # Mock sleep so tests run fast
    @patch("scraper.core.fetcher.requests.Session.get")
    def test_500_retries_and_eventually_fails(self, mock_get, mock_sleep):
        """A 500 server error should retry MAX_RETRIES times then fail."""
        # Arrange
        http_error = HTTPError()
        mock_http_response = MagicMock()
        mock_http_response.status_code = 500
        http_error.response = mock_http_response

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = http_error
        mock_get.return_value = mock_response

        # Act
        response = self.fetcher.fetch(self.request)

        # Assert
        self.assertFalse(response.success)
        # Should have retried MAX_RETRIES times (default: 3)
        self.assertEqual(mock_get.call_count, 3)

    @patch("scraper.core.fetcher.time.sleep")
    @patch("scraper.core.fetcher.requests.Session.get")
    def test_timeout_retries_and_fails(self, mock_get, mock_sleep):
        """A timeout should trigger retry logic."""
        # Arrange
        mock_get.side_effect = Timeout()

        # Act
        response = self.fetcher.fetch(self.request)

        # Assert
        self.assertFalse(response.success)
        self.assertIn("timed out", response.error.lower())
        self.assertEqual(mock_get.call_count, 3)

    @patch("scraper.core.fetcher.requests.Session.get")
    def test_connection_error_returns_failure(self, mock_get):
        """A ConnectionError should be caught and returned as failure."""
        # Arrange
        mock_get.side_effect = ConnectionError()

        # Act
        with patch("scraper.core.fetcher.time.sleep"):
            response = self.fetcher.fetch(self.request)

        # Assert
        self.assertFalse(response.success)
        self.assertIsNotNone(response.error)

    @patch("scraper.core.fetcher.time.sleep")
    @patch("scraper.core.fetcher.requests.Session.get")
    def test_retry_succeeds_on_second_attempt(self, mock_get, mock_sleep):
        """Should succeed if a retry attempt returns 200 after initial failure."""
        # Arrange — first call raises Timeout, second call succeeds
        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.text = "<html><title>Success</title></html>"
        mock_success.raise_for_status = MagicMock()

        mock_get.side_effect = [Timeout(), mock_success]

        # Act
        response = self.fetcher.fetch(self.request)

        # Assert
        self.assertTrue(response.success)
        self.assertEqual(mock_get.call_count, 2)

    @patch("scraper.core.fetcher.requests.Session.get")
    def test_proxy_is_passed_to_request(self, mock_get):
        """Proxy setting from ScrapeRequest should be forwarded to requests."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html></html>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        proxy_request = ScrapeRequest(
            url="https://docs.python.org/3/",
            proxy="http://proxy.example.com:8080",
        )

        # Act
        self.fetcher.fetch(proxy_request)

        # Assert — check proxies kwarg was passed
        call_kwargs = mock_get.call_args.kwargs
        self.assertIn("proxies", call_kwargs)
        self.assertEqual(
            call_kwargs["proxies"],
            {"http": "http://proxy.example.com:8080", "https": "http://proxy.example.com:8080"},
        )

    @patch("scraper.core.fetcher.requests.Session.get")
    def test_browser_flag_routes_to_playwright(self, mock_get):
        """use_browser=True should route to Playwright, not requests."""
        # Arrange — mock Playwright to avoid actually launching a browser
        browser_request = ScrapeRequest(
            url="https://docs.python.org/3/",
            use_browser=True,
        )

        with patch.object(self.fetcher, "_fetch_with_playwright") as mock_playwright:
            mock_playwright.return_value = ScrapeResponse(
                url=browser_request.url,
                status_code=200,
                raw_html="<html></html>",
                success=True,
                used_browser=True,
            )

            # Act
            response = self.fetcher.fetch(browser_request)

        # Assert — requests.get should NOT have been called
        mock_get.assert_not_called()
        mock_playwright.assert_called_once()
        self.assertTrue(response.used_browser)


class TestFetcherSession(unittest.TestCase):
    """Tests for session management."""

    def test_default_session_is_created(self):
        """Fetcher should create a session if none is provided."""
        fetcher = Fetcher()
        self.assertIsNotNone(fetcher.session)
        fetcher.close()

    def test_custom_session_is_used(self):
        """Fetcher should use a provided session instead of creating one."""
        import requests
        custom_session = requests.Session()
        fetcher = Fetcher(session=custom_session)
        self.assertIs(fetcher.session, custom_session)
        fetcher.close()


if __name__ == "__main__":
    unittest.main()