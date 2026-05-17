"""
Unit tests for scraper/core/scraper.py

Tests cover:
- Successful end-to-end scrape pipeline
- Fetch failure propagation (no parse attempted)
- Auto-browser detection for JS-rendered pages
- Auto-browser fallback failure handling
- Context manager cleanup
- Custom fetcher and parser injection
"""

import unittest
from unittest.mock import MagicMock, patch

from scraper.core.scraper import Scraper, MIN_CONTENT_LENGTH
from scraper.models.request import ScrapeRequest
from scraper.models.response import ScrapeResponse


def make_fetch_response(
    url: str = "https://docs.python.org/3/",
    success: bool = True,
    raw_html: str = "<html><title>Test</title><body>" + "<p>Content here.</p>" * 20 + "</body></html>",
    status_code: int = 200,
    used_browser: bool = False,
) -> ScrapeResponse:
    """Helper — build a mock fetch response."""
    return ScrapeResponse(
        url=url,
        status_code=status_code,
        raw_html=raw_html,
        success=success,
        error=None if success else "Fetch failed",
        used_browser=used_browser,
    )


def make_parsed_response(
    url: str = "https://docs.python.org/3/",
    title: str = "Test Page",
    content: str = "This is test content.",
    links: list = None,
) -> ScrapeResponse:
    """Helper — build a mock parsed response."""
    response = ScrapeResponse(
        url=url,
        status_code=200,
        success=True,
        title=title,
        content=content,
        links=links or ["https://docs.python.org/3/tutorial/"],
    )
    return response


class TestScraperPipeline(unittest.TestCase):
    """Tests for the core scrape() pipeline."""

    def setUp(self):
        self.request = ScrapeRequest(url="https://docs.python.org/3/")

    def test_successful_scrape_returns_parsed_response(self):
        """A successful fetch + parse should return a populated response."""
        # Arrange
        mock_fetcher = MagicMock()
        mock_parser = MagicMock()

        fetch_result = make_fetch_response()
        parsed_result = make_parsed_response()

        mock_fetcher.fetch.return_value = fetch_result
        mock_parser.parse.return_value = parsed_result

        scraper = Scraper(fetcher=mock_fetcher, parser=mock_parser)

        # Act
        response = scraper.scrape(self.request)

        # Assert
        self.assertTrue(response.success)
        self.assertEqual(response.title, "Test Page")
        self.assertEqual(response.content, "This is test content.")
        mock_fetcher.fetch.assert_called_once_with(self.request)
        mock_parser.parse.assert_called_once_with(fetch_result)

    def test_fetch_failure_skips_parser(self):
        """If fetch fails, parser should never be called."""
        # Arrange
        mock_fetcher = MagicMock()
        mock_parser = MagicMock()

        mock_fetcher.fetch.return_value = make_fetch_response(
            success=False,
            raw_html="",
            status_code=-1,
        )

        scraper = Scraper(fetcher=mock_fetcher, parser=mock_parser)

        # Act
        response = scraper.scrape(self.request)

        # Assert
        self.assertFalse(response.success)
        mock_parser.parse.assert_not_called()

    def test_parser_is_called_with_fetch_result(self):
        """Parser should receive the exact response object from fetcher."""
        # Arrange
        mock_fetcher = MagicMock()
        mock_parser = MagicMock()

        fetch_result = make_fetch_response()
        mock_fetcher.fetch.return_value = fetch_result
        mock_parser.parse.return_value = fetch_result

        scraper = Scraper(fetcher=mock_fetcher, parser=mock_parser)

        # Act
        scraper.scrape(self.request)

        # Assert — parser received exactly what fetcher returned
        mock_parser.parse.assert_called_once_with(fetch_result)


class TestScraperAutoBrowser(unittest.TestCase):
    """Tests for JS-rendering auto-detection."""

    def setUp(self):
        self.request = ScrapeRequest(url="https://docs.python.org/3/")

    def test_sparse_content_triggers_playwright_retry(self):
        """A response with very little HTML should trigger a Playwright retry."""
        # Arrange
        mock_fetcher = MagicMock()
        mock_parser = MagicMock()

        # First fetch returns suspiciously sparse HTML (JS shell)
        sparse_html = "<html><body><div id='app'></div></body></html>"
        assert len(sparse_html) < MIN_CONTENT_LENGTH  # confirm it's sparse

        first_response = make_fetch_response(raw_html=sparse_html)
        browser_response = make_fetch_response(
            raw_html="<html><title>Full</title><body><p>Full content</p></body></html>",
            used_browser=True,
        )

        # First call → sparse, second call → browser response
        mock_fetcher.fetch.side_effect = [first_response, browser_response]
        mock_parser.parse.return_value = make_parsed_response()

        scraper = Scraper(fetcher=mock_fetcher, parser=mock_parser, auto_browser=True)

        # Act
        scraper.scrape(self.request)

        # Assert — fetcher was called twice (once static, once browser)
        self.assertEqual(mock_fetcher.fetch.call_count, 2)

        # Second call should have use_browser=True
        second_call_request = mock_fetcher.fetch.call_args_list[1][0][0]
        self.assertTrue(second_call_request.use_browser)

    def test_rich_content_does_not_trigger_playwright(self):
        """A response with sufficient HTML should not trigger Playwright."""
        # Arrange
        mock_fetcher = MagicMock()
        mock_parser = MagicMock()

        rich_html = "<html><title>Rich</title><body>" + "<p>content</p>" * 20 + "</body></html>"
        assert len(rich_html) >= MIN_CONTENT_LENGTH

        mock_fetcher.fetch.return_value = make_fetch_response(raw_html=rich_html)
        mock_parser.parse.return_value = make_parsed_response()

        scraper = Scraper(fetcher=mock_fetcher, parser=mock_parser, auto_browser=True)

        # Act
        scraper.scrape(self.request)

        # Assert — fetcher only called once, no Playwright retry
        mock_fetcher.fetch.assert_called_once()

    def test_auto_browser_disabled_skips_playwright(self):
        """auto_browser=False should never trigger a Playwright retry."""
        # Arrange
        mock_fetcher = MagicMock()
        mock_parser = MagicMock()

        sparse_html = "<html><body></body></html>"
        mock_fetcher.fetch.return_value = make_fetch_response(raw_html=sparse_html)
        mock_parser.parse.return_value = make_parsed_response()

        scraper = Scraper(fetcher=mock_fetcher, parser=mock_parser, auto_browser=False)

        # Act
        scraper.scrape(self.request)

        # Assert — fetcher called once only, no retry
        mock_fetcher.fetch.assert_called_once()

    def test_explicit_browser_request_skips_auto_detection(self):
        """use_browser=True on the request should skip auto-detection entirely."""
        # Arrange
        mock_fetcher = MagicMock()
        mock_parser = MagicMock()

        sparse_html = "<html><body></body></html>"
        mock_fetcher.fetch.return_value = make_fetch_response(
            raw_html=sparse_html, used_browser=True
        )
        mock_parser.parse.return_value = make_parsed_response()

        browser_request = ScrapeRequest(
            url="https://docs.python.org/3/",
            use_browser=True,
        )
        scraper = Scraper(fetcher=mock_fetcher, parser=mock_parser)

        # Act
        scraper.scrape(browser_request)

        # Assert — only one fetch, no second attempt
        mock_fetcher.fetch.assert_called_once()

    def test_playwright_fallback_failure_uses_original_response(self):
        """If Playwright retry also fails, scraper proceeds with original response."""
        # Arrange
        mock_fetcher = MagicMock()
        mock_parser = MagicMock()

        sparse_html = "<html><body></body></html>"
        first_response = make_fetch_response(raw_html=sparse_html)
        failed_browser_response = make_fetch_response(
            success=False, raw_html="", status_code=-1
        )

        mock_fetcher.fetch.side_effect = [first_response, failed_browser_response]
        mock_parser.parse.return_value = first_response

        scraper = Scraper(fetcher=mock_fetcher, parser=mock_parser, auto_browser=True)

        # Act — should not raise
        response = scraper.scrape(self.request)

        # Assert — parser still called with original response
        mock_parser.parse.assert_called_once_with(first_response)


class TestScraperContextManager(unittest.TestCase):
    """Tests for context manager support."""

    def test_context_manager_calls_close_on_exit(self):
        """Exiting a with block should call close() automatically."""
        mock_fetcher = MagicMock()
        mock_parser = MagicMock()

        with Scraper(fetcher=mock_fetcher, parser=mock_parser):
            pass

        mock_fetcher.close.assert_called_once()

    def test_context_manager_calls_close_on_exception(self):
        """close() should be called even if an exception is raised inside with block."""
        mock_fetcher = MagicMock()
        mock_parser = MagicMock()

        try:
            with Scraper(fetcher=mock_fetcher, parser=mock_parser):
                raise ValueError("Simulated error")
        except ValueError:
            pass

        # close() must still have been called despite the exception
        mock_fetcher.close.assert_called_once()


class TestScraperDefaults(unittest.TestCase):
    """Tests for default initialization behavior."""

    def test_default_fetcher_is_created(self):
        """Scraper should create a Fetcher if none is provided."""
        from scraper.core.fetcher import Fetcher
        scraper = Scraper()
        self.assertIsInstance(scraper.fetcher, Fetcher)
        scraper.close()

    def test_default_parser_is_created(self):
        """Scraper should create a Parser if none is provided."""
        from scraper.core.parser import Parser
        scraper = Scraper()
        self.assertIsInstance(scraper.parser, Parser)
        scraper.close()

    def test_custom_fetcher_and_parser_are_used(self):
        """Injected fetcher and parser should be used instead of defaults."""
        mock_fetcher = MagicMock()
        mock_parser = MagicMock()

        scraper = Scraper(fetcher=mock_fetcher, parser=mock_parser)
        self.assertIs(scraper.fetcher, mock_fetcher)
        self.assertIs(scraper.parser, mock_parser)


if __name__ == "__main__":
    unittest.main()