import time
from typing import List

import httpx

from app.config import settings
from app.logger import logger
from app.search.providers.base import ProviderError, SearchProvider, SearchResult


class ExaSearchProvider(SearchProvider):
    """Exa.ai search provider (Primary)."""

    def __init__(self, api_key: str | None = None, timeout: float = 10.0):
        self.api_key = api_key or settings.EXA_API_KEY
        self.timeout = timeout
        self.base_url = "https://api.exa.ai/search"

    def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        if not self.api_key or self.api_key.strip() == "":
            raise ProviderError("EXA_API_KEY is not configured")

        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "NextStopRecruiting/1.0",
        }
        payload = {
            "query": query,
            "numResults": num_results,
            "useAutoprompt": True,
            "contents": {"highlights": {"numSentences": 2}},
        }

        # Retry once with backoff
        for attempt in (1, 2):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(self.base_url, headers=headers, json=payload)
                    if resp.status_code >= 400:
                        raise ProviderError(f"Exa search failed: {resp.status_code} - {resp.text}")
                    data = resp.json()
                    results: List[SearchResult] = []
                    for r in data.get("results", []):
                        pub_date = r.get("published_date") or r.get("publishedDate") or r.get("date")
                        highlights = r.get("highlights")
                        if isinstance(highlights, list):
                            highlight_text = " ".join(str(h) for h in highlights if h)
                        elif isinstance(highlights, str):
                            highlight_text = highlights
                        else:
                            highlight_text = ""
                        snippet = highlight_text or r.get("text", "") or r.get("highlight", "") or ""
                        results.append(
                            SearchResult(
                                url=r.get("url", ""),
                                title=r.get("title", ""),
                                snippet=snippet,
                                score=r.get("score"),
                                published_date=str(pub_date) if pub_date else None,
                            )
                        )
                    return results
            except (httpx.RequestError, ProviderError) as exc:
                if attempt == 1:
                    logger.warning(f"Exa search attempt 1 failed: {exc}. Retrying with backoff...")
                    time.sleep(0.5)
                else:
                    raise ProviderError(f"Exa search provider failed after retrying: {exc}") from exc

        return []
