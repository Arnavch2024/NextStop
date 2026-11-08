from abc import ABC, abstractmethod
from typing import List, Optional

from pydantic import BaseModel


class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str = ""
    score: Optional[float] = None
    page_text: Optional[str] = None
    linkedin: bool = False


class ProviderError(Exception):
    """Raised when an external search provider fails or times out."""

    pass


class SearchProvider(ABC):
    """Abstract interface for swappable search providers."""

    @abstractmethod
    def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """Executes search and returns a list of SearchResult objects."""
        pass
