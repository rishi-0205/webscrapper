# webscrapper

A production-grade, pure Python web scraper built from scratch with no third-party scraping frameworks. Accepts a single URL, fetches the page using either static HTTP requests or a headless browser, parses the HTML into clean structured content, and saves the result as a JSON file.

---

## Features

- **Dual fetching strategy** — static (`requests`) for plain HTML pages, Playwright for JS-rendered pages
- **Auto-detection** — automatically detects JS-rendered pages and retries with a headless browser
- **Header rotation** — rotates through a pool of real Chrome, Firefox, Safari, and Edge user agents per request
- **Exponential backoff** — retries failed requests with increasing wait times (2s → 4s → 8s)
- **Smart retry logic** — retries server errors (5xx) but never client errors (4xx) that won't resolve
- **Proxy support** — architecture is proxy-aware from day one via optional proxy field
- **Structured logging** — logs to both console and file with timestamps, log levels, and module tracking
- **Abstract storage** — swappable storage backends via abstract base class (JSON now, PostgreSQL later)
- **Clean data models** — strict typed `dataclasses` for input and output contracts
- **45 passing tests** — full test suite with zero real HTTP requests (all mocked)
- **CLI interface** — run from terminal with URL arguments and flags

---

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [File Breakdown](#file-breakdown)
- [Configuration](#configuration)
- [Testing](#testing)
- [Design Decisions](#design-decisions)

---

## Installation

**1. Clone the repository**
```bash
git clone https://github.com/yourusername/webscrapper.git
cd webscrapper
```

**2. Create and activate a virtual environment**
```bash
# Create
python -m venv venv

# Activate — Windows
venv\Scripts\activate

# Activate — Mac/Linux
source venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
playwright install chromium
```

---

## Usage

**Scrape the default URL** *(set `DEFAULT_URL` in `main.py`)*
```bash
python main.py
```

**Scrape a specific URL**
```bash
python main.py https://docs.python.org/3/
```

**Force browser mode** *(for JS-rendered pages)*
```bash
python main.py https://example.com --browser
```

**Print result without saving to file**
```bash
python main.py https://docs.python.org/3/ --no-save
```

**Use a proxy**
```bash
python main.py https://docs.python.org/3/ --proxy http://user:pass@host:port
```

### Example Output

```
────────────────────────────────────────────────────────────
  ✅ SCRAPE SUCCESSFUL
────────────────────────────────────────────────────────────
  URL          : https://docs.python.org/3/
  Status       : 200
  Title        : 3.13.3 Documentation
  Content      : 8,421 characters
  Links found  : 134
  Browser used : No
  Scraped at   : 2026-05-05 18:09:43 UTC
────────────────────────────────────────────────────────────

📄 Content Preview:

Welcome to Python 3.13...

🔗 First 5 Links:
   https://docs.python.org/3/whatsnew/3.13.html
   https://docs.python.org/3/tutorial/index.html
   https://docs.python.org/3/library/index.html
   https://docs.python.org/3/reference/index.html
   https://docs.python.org/3/howto/index.html
   ... and 129 more
```

### Use as a Library

```python
from scraper.core.scraper import Scraper
from scraper.models.request import ScrapeRequest
from scraper.storage.json_storage import JsonStorage

# Recommended — context manager handles cleanup automatically
with Scraper() as scraper:
    request = ScrapeRequest(url="https://docs.python.org/3/")
    response = scraper.scrape(request)

if response.success:
    print(response.title)
    print(response.content)
    print(response.links)

    # Save to JSON
    storage = JsonStorage()
    storage.save(response)
```

---

## Project Structure

```
webscrapper/
│
├── scraper/                        # Main package
│   ├── __init__.py
│   │
│   ├── core/                       # Heart of the scraper
│   │   ├── __init__.py
│   │   ├── fetcher.py              # All HTTP logic — static and browser-based
│   │   ├── parser.py               # HTML parsing and content extraction
│   │   └── scraper.py              # Orchestrator — ties fetcher and parser together
│   │
│   ├── models/                     # Data shapes and contracts
│   │   ├── __init__.py
│   │   ├── request.py              # ScrapeRequest — defines what goes IN
│   │   └── response.py             # ScrapeResponse — defines what comes OUT
│   │
│   ├── storage/                    # Where results are saved
│   │   ├── __init__.py
│   │   ├── base.py                 # Abstract storage interface (BaseStorage)
│   │   └── json_storage.py         # JSON file implementation of BaseStorage
│   │
│   ├── utils/                      # Shared helper tools
│   │   ├── __init__.py
│   │   ├── logger.py               # Centralized structured logging
│   │   ├── headers.py              # Browser-like HTTP header generation
│   │   └── url.py                  # URL validation, normalization, resolution
│   │
│   └── config/                     # All settings in one place
│       ├── __init__.py
│       └── settings.py             # Single source of truth for all config values
│
├── tests/                          # Mirrors scraper/ package structure
│   ├── __init__.py
│   ├── test_fetcher.py             # 9 tests
│   ├── test_parser.py              # 15 tests
│   └── test_scraper.py             # 21 tests
│
├── output/                         # Scraped JSON results saved here
├── logs/                           # scraper.log written here
├── main.py                         # CLI entry point
├── requirements.txt
└── .gitignore
```

---

## Architecture

The scraper is built around strict separation of concerns. Each layer has one responsibility and knows nothing about the others. External code only ever talks to `Scraper` — never directly to `Fetcher`, `Parser`, or storage.

```
┌─────────────────────────────────────────────────┐
│                   main.py / caller              │
│         ScrapeRequest(url="https://...")        │
└───────────────────────┬─────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────┐
│              Scraper (orchestrator)             │
│  - Calls Fetcher, then Parser                  │
│  - Auto-detects JS rendering                   │
│  - Measures timing                             │
│  - Handles cleanup                             │
└───────────┬─────────────────────────┬───────────┘
            │                         │
            ▼                         ▼
┌───────────────────┐     ┌───────────────────────┐
│      Fetcher      │     │        Parser         │
│                   │     │                       │
│  requests.get()   │     │  Remove noise tags    │
│  Playwright       │     │  Extract title        │
│  Retry + backoff  │     │  Extract content      │
│  Header rotation  │     │  Extract links        │
│  Proxy support    │     │  Clean text           │
└─────────┬─────────┘     └───────────┬───────────┘
          │                           │
          ▼                           ▼
┌─────────────────────────────────────────────────┐
│           ScrapeResponse (data model)           │
│  url, status_code, raw_html, title,             │
│  content, links, success, error, scraped_at     │
└───────────────────────┬─────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────┐
│              Storage (abstract)                 │
│  BaseStorage → JsonStorage (default)            │
│              → PostgresStorage (future)         │
└─────────────────────────────────────────────────┘
```

### Fetching Pipeline

```
ScrapeRequest received
        │
        ├── use_browser=False → requests.get() with browser-like headers
        │         │
        │         ├── Success (2xx) → return raw HTML
        │         ├── 4xx error    → fail immediately, no retry
        │         ├── 5xx error    → retry with exponential backoff
        │         └── Timeout      → retry with exponential backoff
        │
        └── use_browser=True → Playwright headless Chromium
                  │
                  ├── Navigate to URL
                  ├── Wait for networkidle (JS fully executed)
                  └── Capture fully rendered HTML
```

### Auto JS-Detection

```
Static fetch returns HTML
        │
        └── len(raw_html) < 200 chars?
                  │
                  ├── NO  → proceed to parser normally
                  │
                  └── YES → page is likely a JS shell
                            retry with Playwright automatically
```

### Parsing Pipeline

```
raw_html received
        │
        ├── Step 1: Remove noise tags (script, style, nav, footer, header, aside, form)
        ├── Step 2: Extract title (<title> → <h1> → <h2> → "")
        ├── Step 3: Extract content (p, h1-h6, li, code, pre)
        ├── Step 4: Extract & resolve links (absolute + relative → validated → deduplicated)
        └── Step 5: Clean text (unicode NFKC, collapse whitespace, strip \xa0)
```

---

## File Breakdown

### `scraper/config/settings.py`
Single source of truth for every configuration value. No magic numbers anywhere else in the codebase. Uses `pathlib.Path` for cross-platform paths that work on Windows, Mac, and Linux without modification. Automatically creates `output/` and `logs/` directories on import.

| Constant | Value | Purpose |
|---|---|---|
| `REQUEST_TIMEOUT` | `30` | Seconds before request gives up |
| `MAX_RETRIES` | `3` | Max retry attempts per request |
| `RETRY_DELAY` | `2` | Base seconds for exponential backoff |
| `PLAYWRIGHT_HEADLESS` | `True` | Run browser without visible window |
| `PLAYWRIGHT_TIMEOUT` | `30000` | Milliseconds for Playwright page load |
| `CONTENT_TAGS` | `["p", "h1"...]` | HTML tags to extract text from |
| `NOISE_TAGS` | `["script", "nav"...]` | HTML tags to remove before parsing |
| `LOG_LEVEL` | `"DEBUG"` | Logging verbosity |

---

### `scraper/utils/logger.py`
Centralized logger — all modules call `get_logger(__name__)` instead of `print()`. Sets up one root logger with two handlers:

- **Console handler** — clean, human-readable format
- **File handler** — detailed format with filename and line number

A guard prevents duplicate log lines when multiple modules import the logger.

```python
# Every module uses this pattern
from scraper.utils.logger import get_logger
logger = get_logger(__name__)

logger.debug("Detailed info for development")
logger.info("General progress")
logger.warning("Unexpected but not fatal")
logger.error("Something failed")
```

---

### `scraper/models/request.py` — `ScrapeRequest`

Input contract. Validated and normalized in `__post_init__` before anything else runs.

```python
@dataclass
class ScrapeRequest:
    url: str                          # Required — must be http:// or https://
    use_browser: bool = False         # Force Playwright for JS pages
    timeout: int = 30                 # Seconds before giving up
    headers: dict = {}                # Custom headers merged over defaults
    tags: list[str] = CONTENT_TAGS   # HTML tags to extract content from
    proxy: str = None                 # Optional: "http://user:pass@host:port"
```

Validation raises clear errors immediately:
- Empty URL → `ValueError`
- Non-http URL → `ValueError`
- Negative timeout → `ValueError`

Normalization strips whitespace and removes URL fragments (`#section`) before the URL travels any further into the system.

---

### `scraper/models/response.py` — `ScrapeResponse`

Output contract. Always returned — even on failure. Check `response.success` before using data.

```python
@dataclass
class ScrapeResponse:
    url: str                          # The URL that was scraped
    status_code: int = -1            # HTTP status (-1 = never completed)
    raw_html: str = ""               # Transient — not saved to storage
    title: str = ""                  # Populated by Parser
    content: str = ""                # Populated by Parser
    links: list[str] = []            # Populated by Parser
    success: bool = False            # True if pipeline completed
    error: str = None                # Error message if success=False
    scraped_at: datetime             # UTC timestamp, auto-set
    used_browser: bool = False       # Whether Playwright was used
```

`to_dict()` serializes for storage (excludes `raw_html`, converts `datetime` to ISO 8601).
`summary()` returns a one-line human-readable log string.

---

### `scraper/utils/url.py`

All URL cleaning happens here before anything else touches a URL. Uses Python's built-in `urllib.parse` — no extra dependencies.

| Function | Purpose |
|---|---|
| `is_valid_url(url)` | Returns True if URL has valid http/https scheme and domain |
| `normalize_url(url)` | Lowercases scheme/domain, removes fragments, sorts query params, ensures trailing slash |
| `extract_domain(url)` | Returns netloc (e.g. `docs.python.org`) |
| `resolve_relative_url(base, relative)` | Resolves `/tutorial/` against `https://docs.python.org/3/` → absolute URL |

> `is_same_domain` is intentionally absent — it is a crawler concern, not a scraper concern. The crawler project will have its own `url.py`.

---

### `scraper/utils/headers.py`

Generates realistic browser-like HTTP headers. A static User-Agent is one of the easiest bot signals — rotating through real browser strings significantly reduces detection.

Pool of 6 User-Agent strings across:
- Chrome on Windows and macOS
- Firefox on Windows and macOS
- Safari on macOS
- Edge on Windows

| Function | Purpose |
|---|---|
| `get_default_headers(randomize=True)` | Full set of browser-like headers with random UA |
| `get_headers_for_url(url)` | Adds `Origin`, `Referer`, and `Host` specific to the URL |
| `merge_headers(base, custom)` | Merges custom headers over defaults — custom wins on conflict |

---

### `scraper/core/fetcher.py` — `Fetcher`

The only file that makes network requests. Takes a `ScrapeRequest`, returns a `ScrapeResponse` with `raw_html` populated.

**Static fetching (`requests`):**
- Uses a persistent `requests.Session` for TCP connection reuse (keep-alive)
- Retries up to `MAX_RETRIES` with exponential backoff
- Never retries 4xx client errors — they won't resolve on retry
- Always retries 5xx server errors and timeouts

**Dynamic fetching (Playwright):**
- Launches headless Chromium
- Waits for `networkidle` — no network activity for 500ms means JS has fully executed
- Playwright is imported inside the method only when needed — keeps startup fast for static-only use

**Error handling (every path returns a response, never crashes):**
- `HTTPError` — catches and categorizes 4xx vs 5xx
- `Timeout` — caught and retried
- `TooManyRedirects` — caught, not retried (redirect loop won't resolve)
- `ConnectionError` — caught and retried
- `Exception` — any unexpected error caught as last resort

---

### `scraper/core/parser.py` — `Parser`

Parses `raw_html` and populates `title`, `content`, and `links` on the response object. Order of operations is critical — noise must be removed before content is extracted.

**Step 1 — Noise removal:**
`element.decompose()` is used over `element.extract()` — decompose removes the element AND frees memory, which matters on large pages.

**Step 2 — Title extraction (with fallbacks):**
`<title>` tag → `<h1>` → `<h2>` → empty string. Real-world pages don't always have every tag.

**Step 3 — Content extraction:**
`get_text(separator=" ")` is used over `get_text()` — without a separator, `<p>Hello<span>World</span></p>` becomes `"HelloWorld"`. With separator it becomes `"Hello World"`.

**Step 4 — Link extraction:**
- Skips `#`, `mailto:`, `tel:`, `javascript:` hrefs
- Resolves relative URLs to absolute using `resolve_relative_url()`
- Deduplicates using a `set` for O(1) lookup regardless of page size

**Step 5 — Text cleaning:**
- `unicodedata.normalize("NFKC")` — converts fancy quotes, ligatures, special spaces
- `\xa0` non-breaking spaces replaced with regular spaces
- Multiple consecutive spaces and newlines collapsed

---

### `scraper/core/scraper.py` — `Scraper`

The orchestrator. The only file that knows `Fetcher` and `Parser` both exist. All external code talks only to this class.

```python
# Recommended usage
with Scraper() as scraper:
    response = scraper.scrape(ScrapeRequest(url="https://..."))
```

Key behaviors:
- **Context manager** (`__enter__`/`__exit__`) — guarantees `close()` is called even if an exception occurs
- **Dependency injection** — `Fetcher` and `Parser` are passed in via constructor, making testing trivial
- **Immutable requests** — `_make_browser_request()` creates a new `ScrapeRequest` instead of mutating the original
- **Auto-browser threshold** — `MIN_CONTENT_LENGTH = 200` chars; below this the page is retried with Playwright
- **Timing** — wraps entire pipeline in `time.time()` for performance visibility in logs

---

### `scraper/storage/base.py` — `BaseStorage`

Abstract base class using Python's `abc.ABC`. Any subclass that fails to implement an abstract method raises `TypeError` at instantiation — Python enforces the contract automatically.

```python
class BaseStorage(ABC):
    @abstractmethod
    def save(self, response: ScrapeResponse) -> bool: ...

    @abstractmethod
    def load(self, url: str) -> ScrapeResponse | None: ...

    @abstractmethod
    def exists(self, url: str) -> bool: ...

    @abstractmethod
    def delete(self, url: str) -> bool: ...

    @abstractmethod
    def all(self) -> list[ScrapeResponse]: ...

    def save_many(self, responses) -> dict: ...  # Concrete — free for all subclasses
```

---

### `scraper/storage/json_storage.py` — `JsonStorage`

Concrete `BaseStorage` implementation. Saves each `ScrapeResponse` as an individual `.json` file.

**File naming:**
```
https://docs.python.org/3/tutorial/ → docs.python.org_3_tutorial_.json
```
Scheme stripped → unsafe characters replaced with `_` → consecutive `_` collapsed → capped at 200 chars.

**Round-trip datetime handling:**
- On save: `scraped_at` datetime → ISO 8601 string via `to_dict()`
- On load: ISO 8601 string → datetime via `datetime.fromisoformat()`

`raw_html` is excluded from both save and load — it is transient and not needed after parsing.

---

## Configuration

All configuration lives in `scraper/config/settings.py`. Edit values there — never hardcode in other files.

```python
REQUEST_TIMEOUT = 30          # Increase for slow sites
MAX_RETRIES = 3               # Increase for unreliable connections
RETRY_DELAY = 2               # Base seconds for exponential backoff
PLAYWRIGHT_HEADLESS = True    # Set False to watch browser during development
LOG_LEVEL = "DEBUG"           # Change to "INFO" to reduce log verbosity

CONTENT_TAGS = [              # Add tags here to extract more content types
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "code", "pre"
]

NOISE_TAGS = [                # Add tags here to remove more noise
    "script", "style", "nav",
    "footer", "header", "aside", "form"
]
```

---

## Testing

**Run all tests**
```bash
python -m pytest tests/ -v
```

**Run a specific file**
```bash
python -m pytest tests/test_parser.py -v
```

**Run a specific test class**
```bash
python -m pytest tests/test_scraper.py::TestScraperAutoBrowser -v
```

**Run a single test**
```bash
python -m pytest tests/test_scraper.py::TestScraperAutoBrowser::test_sparse_content_triggers_playwright_retry -v
```

**Stop at first failure**
```bash
python -m pytest tests/ -v -x
```

### Test Coverage

| File | Classes | Tests | What's covered |
|---|---|---|---|
| `test_fetcher.py` | 2 | 9 | Successful fetch, 404 no-retry, 500 retry, timeout retry, connection error, retry success on attempt 2, proxy forwarding, browser routing, session management |
| `test_parser.py` | 4 | 15 | Title tag, h1/h2 fallbacks, no title, paragraph extraction, noise removal, empty HTML, custom tags, headings, absolute links, relative link resolution, fragment/mailto/javascript/empty href exclusion, deduplication, unicode cleaning, malformed HTML resilience |
| `test_scraper.py` | 4 | 21 | Successful pipeline, fetch failure skips parser, parser receives fetch result, sparse content triggers Playwright, rich content does not, auto_browser=False, explicit browser skips detection, Playwright fallback failure, context manager cleanup on success and exception, default and custom injection |

**Testing patterns used:**
- `MagicMock` — injects fake fetcher/parser with no real network calls
- `side_effect` with lists — simulates retry sequences (fail, fail, succeed)
- `@patch("scraper.core.fetcher.time.sleep")` — makes retry tests instant
- `make_fetch_response()` / `make_parsed_response()` — shared helpers avoid repetition across tests

---

## Design Decisions

**Fetcher imports Playwright inside the method**
`from playwright.sync_api import sync_playwright` lives inside `_fetch_with_playwright()`, not at the top of the file. Playwright is never loaded unless `use_browser=True` is requested — keeping startup fast for the common static-page case.

**`element.decompose()` over `element.extract()`**
Both remove an element from the BeautifulSoup tree, but `decompose()` also frees the memory the element was using. For large pages with many noise elements, this matters.

**4xx errors are not retried**
A `404 Not Found` or `403 Forbidden` is a definitive answer from the server — retrying it wastes time and adds unnecessary load. Only `5xx` server errors and network failures are worth retrying.

**`raw_html` excluded from storage**
Raw HTML can be several megabytes per page. After the parser has extracted title, content, and links, raw HTML is never needed again. Storing it would bloat the output directory with data that provides no value.

**Abstract storage from day one**
Starting with `BaseStorage` → `JsonStorage` instead of writing JSON logic directly means switching to PostgreSQL later requires writing one new class and changing one import in `main.py`. Nothing else in the codebase changes.

**`is_same_domain` excluded from `url.py`**
This scraper processes one URL at a time and never needs to compare domains. The function is intentionally absent — it belongs in a crawler, not a scraper. The `url.py` contains only functions this project actually uses.

**`_make_browser_request()` creates a new object**
Never mutate a caller's input. Creating a new `ScrapeRequest` with `use_browser=True` instead of modifying the original means the caller's object is never changed by a side effect they didn't ask for.

**Proxy-aware architecture without full implementation**
The `proxy` field exists on `ScrapeRequest` and is forwarded to both `requests` and Playwright. A full `ProxyManager` with rotation, health checking, and failover is deferred — documentation sites have no aggressive anti-bot protection, so it is not needed yet. The architecture supports adding it without changing any other file.

---

## Dependencies

```
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=5.1.0
playwright>=1.43.0
pytest>=8.0.0
```

```bash
pip install requests beautifulsoup4 lxml playwright pytest
playwright install chromium
```

---

## License

MIT
