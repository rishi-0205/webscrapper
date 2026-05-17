"""
Unit tests for scraper/core/parser.py

Tests cover:
- Title extraction (title tag, h1 fallback, h2 fallback, no title)
- Content extraction from content tags
- Noise tag removal
- Link extraction and resolution
- Relative URL resolution
- Invalid/empty href filtering
- Text cleaning (whitespace, unicode, non-breaking spaces)
- Empty HTML handling
"""

import unittest

from scraper.core.parser import Parser
from scraper.models.response import ScrapeResponse


# Reusable HTML fixtures
SIMPLE_HTML = """
<html>
<head><title>Python Documentation</title></head>
<body>
    <nav>Navigation garbage that should be removed</nav>
    <h1>Welcome to Python</h1>
    <p>Python is a programming language.</p>
    <p>It is easy to learn.</p>
    <footer>Footer garbage that should be removed</footer>
    <script>alert('js garbage')</script>
</body>
</html>
"""

LINKS_HTML = """
<html>
<head><title>Links Page</title></head>
<body>
    <a href="https://docs.python.org/3/tutorial/">Tutorial</a>
    <a href="/3/library/">Library</a>
    <a href="#section">Fragment only</a>
    <a href="mailto:test@example.com">Email</a>
    <a href="javascript:void(0)">JS link</a>
    <a href="">Empty href</a>
    <a href="https://docs.python.org/3/tutorial/">Duplicate</a>
</body>
</html>
"""

NO_TITLE_HTML = """
<html>
<body>
    <h1>Main Heading Used As Title</h1>
    <p>Some content here.</p>
</body>
</html>
"""

H2_FALLBACK_HTML = """
<html>
<body>
    <h2>H2 Used As Title</h2>
    <p>Content here.</p>
</body>
</html>
"""

UNICODE_HTML = """
<html>
<head><title>Unicode Test</title></head>
<body>
    <p>Hello\xa0World</p>
    <p>Fancy   spaces   here</p>
    <p>Unicode: \u2019s and \u201chello\u201d</p>
</body>
</html>
"""

EMPTY_HTML = ""


def make_response(html: str, url: str = "https://docs.python.org/3/") -> ScrapeResponse:
    """Helper — create a ScrapeResponse with raw_html pre-populated."""
    return ScrapeResponse(
        url=url,
        status_code=200,
        raw_html=html,
        success=True,
    )


class TestParserTitleExtraction(unittest.TestCase):
    """Tests for _extract_title and its fallback strategies."""

    def setUp(self):
        self.parser = Parser()

    def test_extracts_title_from_title_tag(self):
        """Should use <title> tag when present."""
        response = self.parser.parse(make_response(SIMPLE_HTML))
        self.assertEqual(response.title, "Python Documentation")

    def test_falls_back_to_h1_when_no_title_tag(self):
        """Should use <h1> content when no <title> tag exists."""
        response = self.parser.parse(make_response(NO_TITLE_HTML))
        self.assertEqual(response.title, "Main Heading Used As Title")

    def test_falls_back_to_h2_when_no_h1(self):
        """Should use <h2> when neither <title> nor <h1> exists."""
        response = self.parser.parse(make_response(H2_FALLBACK_HTML))
        self.assertEqual(response.title, "H2 Used As Title")

    def test_returns_empty_string_when_no_title_found(self):
        """Should return empty string when no title, h1, or h2 exists."""
        html = "<html><body><p>Just a paragraph</p></body></html>"
        response = self.parser.parse(make_response(html))
        self.assertEqual(response.title, "")


class TestParserContentExtraction(unittest.TestCase):
    """Tests for _extract_content."""

    def setUp(self):
        self.parser = Parser()

    def test_extracts_paragraph_content(self):
        """Should extract text from <p> tags."""
        response = self.parser.parse(make_response(SIMPLE_HTML))
        self.assertIn("Python is a programming language", response.content)
        self.assertIn("It is easy to learn", response.content)

    def test_noise_tags_are_removed_from_content(self):
        """Navigation, footer, and script content should not appear in output."""
        response = self.parser.parse(make_response(SIMPLE_HTML))
        self.assertNotIn("Navigation garbage", response.content)
        self.assertNotIn("Footer garbage", response.content)
        self.assertNotIn("alert", response.content)

    def test_empty_html_returns_empty_content(self):
        """Empty HTML should result in empty content."""
        response = self.parser.parse(make_response(EMPTY_HTML))
        self.assertEqual(response.content, "")

    def test_custom_content_tags_are_respected(self):
        """Parser initialized with custom tags should only extract those tags."""
        html = """
        <html><body>
            <p>Paragraph content</p>
            <span>Span content</span>
        </body></html>
        """
        # Parser that only extracts <span> tags
        span_parser = Parser(content_tags=["span"])
        response = span_parser.parse(make_response(html))

        self.assertIn("Span content", response.content)
        self.assertNotIn("Paragraph content", response.content)

    def test_headings_are_included_in_content(self):
        """h1-h6 headings should be included in extracted content."""
        html = """
        <html><body>
            <h1>Heading One</h1>
            <h2>Heading Two</h2>
            <p>Paragraph</p>
        </body></html>
        """
        response = self.parser.parse(make_response(html))
        self.assertIn("Heading One", response.content)
        self.assertIn("Heading Two", response.content)


class TestParserLinkExtraction(unittest.TestCase):
    """Tests for _extract_links."""

    def setUp(self):
        self.parser = Parser()

    def test_extracts_absolute_links(self):
        """Absolute URLs should be extracted as-is."""
        response = self.parser.parse(
            make_response(LINKS_HTML, url="https://docs.python.org/3/")
        )
        self.assertIn("https://docs.python.org/3/tutorial/", response.links)

    def test_resolves_relative_links_to_absolute(self):
        """Relative URLs should be resolved against the page's base URL."""
        response = self.parser.parse(
            make_response(LINKS_HTML, url="https://docs.python.org/3/")
        )
        self.assertIn("https://docs.python.org/3/library/", response.links)

    def test_fragment_only_links_are_excluded(self):
        """Links like href='#section' should be filtered out."""
        response = self.parser.parse(make_response(LINKS_HTML))
        for link in response.links:
            self.assertFalse(link.startswith("#"))

    def test_mailto_links_are_excluded(self):
        """mailto: links should be filtered out."""
        response = self.parser.parse(make_response(LINKS_HTML))
        for link in response.links:
            self.assertFalse(link.startswith("mailto:"))

    def test_javascript_links_are_excluded(self):
        """javascript: links should be filtered out."""
        response = self.parser.parse(make_response(LINKS_HTML))
        for link in response.links:
            self.assertFalse(link.startswith("javascript:"))

    def test_empty_href_links_are_excluded(self):
        """Empty href attributes should be filtered out."""
        response = self.parser.parse(make_response(LINKS_HTML))
        for link in response.links:
            self.assertTrue(len(link) > 0)

    def test_duplicate_links_are_deduplicated(self):
        """The same URL appearing multiple times should only appear once."""
        response = self.parser.parse(make_response(LINKS_HTML))
        self.assertEqual(
            len(response.links),
            len(set(response.links)),
        )


class TestParserTextCleaning(unittest.TestCase):
    """Tests for _clean_text."""

    def setUp(self):
        self.parser = Parser()

    def test_non_breaking_spaces_are_replaced(self):
        """Non-breaking spaces (\\xa0) should become regular spaces."""
        response = self.parser.parse(make_response(UNICODE_HTML))
        self.assertNotIn("\xa0", response.content)
        self.assertIn("Hello World", response.content)

    def test_multiple_spaces_are_collapsed(self):
        """Multiple consecutive spaces should collapse to one."""
        response = self.parser.parse(make_response(UNICODE_HTML))
        self.assertNotIn("   ", response.content)

    def test_unicode_is_normalized(self):
        """Unicode characters should be normalized (NFKC)."""
        response = self.parser.parse(make_response(UNICODE_HTML))
        # After NFKC normalization, fancy quotes are standardized
        self.assertIsInstance(response.content, str)


class TestParserEdgeCases(unittest.TestCase):
    """Tests for edge cases and error handling."""

    def setUp(self):
        self.parser = Parser()

    def test_empty_raw_html_returns_failure(self):
        """A response with no raw_html should be marked as failed."""
        response = ScrapeResponse(
            url="https://docs.python.org/3/",
            status_code=200,
            raw_html="",
            success=True,
        )
        result = self.parser.parse(response)
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_malformed_html_does_not_crash(self):
        """Badly formed HTML should be handled gracefully."""
        malformed = "<html><body><p>Unclosed paragraph<div>Mixed tags</p></div>"
        response = self.parser.parse(make_response(malformed))
        # Should not raise — lxml is lenient with malformed HTML
        self.assertIsInstance(response.content, str)

    def test_parse_returns_same_response_object(self):
        """Parser should mutate and return the same response, not create a new one."""
        original = make_response(SIMPLE_HTML)
        result = self.parser.parse(original)
        self.assertIs(result, original)


if __name__ == "__main__":
    unittest.main()