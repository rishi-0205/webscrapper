"""
JSON file-based storage implementation.
Saves each ScrapeResponse as an individual JSON file inside output/.

File naming:
    Each result is saved as a .json file named after a sanitized
    version of the URL, making files human-readable and traceable:

    https://docs.python.org/3/          → docs.python.org_3_.json
    https://docs.python.org/3/tutorial/ → docs.python.org_3_tutorial_.json

This is the default storage backend. When you're ready for a database,
write PostgresStorage(BaseStorage) and swap it in main.py — nothing
else changes.

Usage:
    from scraper.storage.json_storage import JsonStorage
    from scraper.models.response import ScrapeResponse

    storage = JsonStorage()
    storage.save(response)

    result = storage.load("https://docs.python.org/3/")
    print(result.title)

    all_results = storage.all()
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from scraper.config.settings import OUTPUT_DIR
from scraper.models.response import ScrapeResponse
from scraper.storage.base import BaseStorage
from scraper.utils.logger import get_logger

logger = get_logger(__name__)


class JsonStorage(BaseStorage):
    """
    Stores ScrapeResponse objects as individual JSON files.

    Each URL maps to one JSON file in the output directory.
    File names are derived from the URL for human readability.

    Args:
        output_dir: Directory to save JSON files in.
                    Defaults to settings.OUTPUT_DIR.

    Example:
        storage = JsonStorage()
        storage.save(response)
        loaded = storage.load(response.url)
    """

    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"JsonStorage initialized → {self.output_dir}")

    # =========================================================================
    # INTERFACE IMPLEMENTATION
    # =========================================================================

    def save(self, response: ScrapeResponse) -> bool:
        """
        Save a ScrapeResponse to a JSON file.

        The file is named after the sanitized URL so it's easy to find.
        If a file for this URL already exists, it is overwritten.

        Args:
            response: The ScrapeResponse to persist

        Returns:
            True if saved successfully, False on error
        """
        try:
            filepath = self._url_to_filepath(response.url)
            data = response.to_dict()

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved → {filepath.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to save '{response.url}': {e}")
            return False

    def load(self, url: str) -> ScrapeResponse | None:
        """
        Load a previously saved ScrapeResponse from its JSON file.

        Args:
            url: The URL of the result to load

        Returns:
            Reconstructed ScrapeResponse, or None if not found
        """
        try:
            filepath = self._url_to_filepath(url)

            if not filepath.exists():
                logger.debug(f"No saved result found for: {url}")
                return None

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            response = self._dict_to_response(data)
            logger.debug(f"Loaded → {filepath.name}")
            return response

        except Exception as e:
            logger.error(f"Failed to load '{url}': {e}")
            return None

    def exists(self, url: str) -> bool:
        """
        Check if a JSON file for this URL already exists.

        Args:
            url: The URL to check

        Returns:
            True if a saved result exists, False otherwise
        """
        return self._url_to_filepath(url).exists()

    def delete(self, url: str) -> bool:
        """
        Delete the JSON file for a given URL.

        Args:
            url: The URL whose saved result should be deleted

        Returns:
            True if deleted, False if file not found or error
        """
        try:
            filepath = self._url_to_filepath(url)

            if not filepath.exists():
                logger.warning(f"Cannot delete — file not found: {filepath.name}")
                return False

            filepath.unlink()
            logger.info(f"Deleted → {filepath.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete '{url}': {e}")
            return False

    def all(self) -> list[ScrapeResponse]:
        """
        Load and return all saved ScrapeResponses from the output directory.

        Returns:
            List of ScrapeResponse objects. Empty list if none saved.
        """
        responses = []

        json_files = list(self.output_dir.glob("*.json"))

        if not json_files:
            logger.debug("No saved results found in output directory")
            return []

        for filepath in json_files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                responses.append(self._dict_to_response(data))
            except Exception as e:
                logger.error(f"Failed to load '{filepath.name}': {e}")

        logger.info(f"Loaded {len(responses)} results from storage")
        return responses

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    def _url_to_filepath(self, url: str) -> Path:
        """
        Convert a URL to a safe, human-readable file path.

        Strips the scheme (https://) then replaces every character
        that isn't alphanumeric, a dot, or a hyphen with an underscore.

        Args:
            url: The URL to convert

        Returns:
            Path object pointing to the .json file for this URL

        Example:
            "https://docs.python.org/3/tutorial/"
            → output/docs.python.org_3_tutorial_.json
        """
        # Remove scheme (https:// or http://)
        clean = re.sub(r"^https?://", "", url)

        # Replace unsafe filesystem characters with underscores
        clean = re.sub(r"[^\w\-.]", "_", clean)

        # Collapse multiple consecutive underscores
        clean = re.sub(r"_+", "_", clean)

        # Trim to 200 chars max to avoid OS filename length limits
        clean = clean[:200].strip("_")

        return self.output_dir / f"{clean}.json"

    def _dict_to_response(self, data: dict) -> ScrapeResponse:
        """
        Reconstruct a ScrapeResponse from a deserialized dictionary.

        Handles type conversion for fields that JSON doesn't preserve
        natively — specifically the datetime scraped_at field.

        Args:
            data: Dictionary loaded from a JSON file

        Returns:
            Reconstructed ScrapeResponse object
        """
        # Parse ISO 8601 datetime string back to datetime object
        scraped_at = data.get("scraped_at")
        if scraped_at and isinstance(scraped_at, str):
            scraped_at = datetime.fromisoformat(scraped_at)
        else:
            scraped_at = datetime.now(timezone.utc)

        return ScrapeResponse(
            url=data.get("url", ""),
            status_code=data.get("status_code", -1),
            title=data.get("title", ""),
            content=data.get("content", ""),
            links=data.get("links", []),
            success=data.get("success", False),
            error=data.get("error"),
            scraped_at=scraped_at,
            used_browser=data.get("used_browser", False),
            # raw_html is intentionally not saved or restored —
            # it's a transient field only used during the scrape pipeline
        )