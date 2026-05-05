"""
storage/base.py

Abstract base class defining the storage interface.
Every storage implementation must inherit from this and
implement all abstract methods.

This contract ensures that swapping storage backends
(JSON → PostgreSQL → MongoDB) never requires changes
to any other part of the codebase.

Usage:
    from scraper.storage.base import BaseStorage

    class MyStorage(BaseStorage):
        def save(self, response): ...
        def load(self, url): ...
        def exists(self, url): ...
        def delete(self, url): ...
        def all(self): ...
"""

from abc import ABC, abstractmethod

from scraper.models.response import ScrapeResponse
from scraper.utils.logger import get_logger

logger = get_logger(__name__)


class BaseStorage(ABC):
    """
    Abstract base class for all storage backends.

    Defines the interface every storage implementation must follow.
    Never instantiate this directly — use a concrete subclass like
    JsonStorage instead.

    All methods must be implemented by subclasses. If a subclass
    fails to implement any method, Python raises a TypeError at
    instantiation time — catching the mistake early.
    """

    @abstractmethod
    def save(self, response: ScrapeResponse) -> bool:
        """
        Persist a ScrapeResponse to storage.

        Args:
            response: The ScrapeResponse to save

        Returns:
            True if saved successfully, False otherwise
        """
        ...

    @abstractmethod
    def load(self, url: str) -> ScrapeResponse | None:
        """
        Retrieve a previously saved ScrapeResponse by its URL.

        Args:
            url: The URL of the scrape result to retrieve

        Returns:
            ScrapeResponse if found, None otherwise
        """
        ...

    @abstractmethod
    def exists(self, url: str) -> bool:
        """
        Check if a result for the given URL already exists in storage.

        Useful for avoiding re-scraping pages that are already saved.

        Args:
            url: The URL to check

        Returns:
            True if a result exists, False otherwise
        """
        ...

    @abstractmethod
    def delete(self, url: str) -> bool:
        """
        Delete a stored result by its URL.

        Args:
            url: The URL of the result to delete

        Returns:
            True if deleted successfully, False if not found or failed
        """
        ...

    @abstractmethod
    def all(self) -> list[ScrapeResponse]:
        """
        Retrieve all stored ScrapeResponses.

        Returns:
            List of all ScrapeResponse objects in storage.
            Empty list if nothing is stored.
        """
        ...

    # =========================================================================
    # CONCRETE HELPERS — available to all subclasses for free
    # =========================================================================

    def save_many(self, responses: list[ScrapeResponse]) -> dict:
        """
        Save multiple ScrapeResponses in sequence.

        Concrete method — subclasses get this for free without
        implementing it. Uses self.save() internally so it works
        with any storage backend automatically.

        Args:
            responses: List of ScrapeResponse objects to save

        Returns:
            Dict with counts: {"saved": N, "failed": N, "total": N}
        """
        saved = 0
        failed = 0

        for response in responses:
            if self.save(response):
                saved += 1
            else:
                failed += 1

        result = {"saved": saved, "failed": failed, "total": len(responses)}
        logger.info(f"Bulk save complete: {result}")
        return result