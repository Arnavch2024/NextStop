import urllib.robotparser
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.logger import logger

_robots_cache = {}


def is_linkedin(url: str) -> bool:
    """Returns True if the URL points to LinkedIn (which must never be fetched)."""
    try:
        netloc = urlparse(url).netloc.lower()
        return "linkedin.com" in netloc or "lnkd.in" in netloc
    except Exception:
        return False


def robots_allows(url: str, user_agent: str = "*") -> bool:
    """
    Checks robots.txt for the host.
    Returns True if allowed, False if disallowed.
    """
    if not settings.RESPECT_ROBOTS_TXT:
        return True

    if is_linkedin(url):
        return False

    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if not host:
            return True

        if host in _robots_cache:
            parser = _robots_cache[host]
            return parser.can_fetch(user_agent, url) if parser else True

        robots_url = f"{parsed.scheme or 'https'}://{host}/robots.txt"
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)

        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(robots_url)
                if resp.status_code == 200:
                    parser.parse(resp.text.splitlines())
                    _robots_cache[host] = parser
                    return parser.can_fetch(user_agent, url)
                elif resp.status_code in (401, 403):
                    _robots_cache[host] = None
                    return False
        except Exception:
            pass

        _robots_cache[host] = None
        return True
    except Exception as e:
        logger.debug(f"robots_allows error for {url}: {e}")
        return True


def fetch_page_text(url: str, timeout: float = 8.0) -> Optional[str]:
    """
    Safely fetches page text via Tavily Extract or Jina Reader.
    NEVER fetches LinkedIn pages (returns None).
    Respects robots.txt.
    """
    if is_linkedin(url):
        logger.info(f"Skipping page fetch for LinkedIn URL: {url}")
        return None

    if not robots_allows(url):
        logger.info(f"robots.txt disallows fetching: {url}")
        return None

    provider = settings.WEB_FETCH_PROVIDER
    if not provider:
        return None

    try:
        if provider == "tavily_extract" and settings.TAVILY_API_KEY:
            headers = {"Content-Type": "application/json"}
            payload = {
                "api_key": settings.TAVILY_API_KEY,
                "urls": [url],
            }
            with httpx.Client(timeout=timeout) as client:
                resp = client.post("https://api.tavily.com/extract", headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    if results and len(results) > 0:
                        return results[0].get("raw_content") or results[0].get("content")

        elif provider == "jina_reader":
            headers = {"User-Agent": "NextStopRecruiting/1.0"}
            if settings.JINA_API_KEY:
                headers["Authorization"] = f"Bearer {settings.JINA_API_KEY}"
            reader_url = f"https://r.jina.ai/{url}"
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(reader_url, headers=headers)
                if resp.status_code == 200:
                    return resp.text[:15000]
    except Exception as e:
        logger.warning(f"fetch_page_text failed for {url} via {provider}: {e}")

    return None
