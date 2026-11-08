import re
import urllib.robotparser
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.logger import logger

_robots_cache = {}


def is_data_broker(url: str, blocklist: Optional[List[str]] = None) -> bool:
    """Returns True if the URL points to a commercial people-data aggregator domain."""
    if not url:
        return False
    try:
        netloc = urlparse(url).netloc.lower()
        if ":" in netloc:
            netloc = netloc.split(":")[0]
        domains = blocklist if blocklist is not None else settings.DATA_BROKER_DOMAINS
        for d in domains:
            d_clean = d.strip().lower()
            if not d_clean:
                continue
            if netloc == d_clean or netloc.endswith("." + d_clean):
                return True
        return False
    except Exception:
        return False


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


def normalize_url(url: str) -> str:
    """Normalizes URL for deduplication across providers."""
    if not url:
        return ""
    u = url.strip()
    try:
        parsed = urlparse(u)
        scheme = parsed.scheme.lower() or "https"
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        query = f"?{parsed.query}" if parsed.query else ""
        return f"{scheme}://{netloc}{path}{query}"
    except Exception:
        return u.lower().rstrip("/")


ROLE_OR_COMPANY_KEYWORDS = re.compile(
    r"\b("
    r"recruit(?:er|ing|ment)?|talent|acquisition|campus|university|hiring|early\s+careers?|"
    r"internships?|hr|human\s+resources|placement|lead|manager|director|officer|partner|"
    r"associate|specialist|head|engineer|developer|analyst|consultant|vice\s+president|vp|"
    r"services|solutions|bank|pvt|ltd|limited|inc|corp|corporation|technologies|group"
    r")\b",
    re.IGNORECASE,
)


def is_name_only_empty_snippet(title: str, snippet: Optional[str] = None, page_text: Optional[str] = None) -> bool:
    """
    Returns True if snippet/text is empty AND title contains only a person's name
    (no role or company words). These results have zero information and are skipped before Gemini.
    """
    has_body = bool((snippet and snippet.strip()) or (page_text and page_text.strip()))
    if has_body:
        return False

    clean_title = (title or "").strip()
    if not clean_title:
        return True

    # Strip trailing site indicators e.g. "| LinkedIn" or "- LinkedIn"
    cleaned = re.sub(
        r"\s*[|–—\-]\s*(LinkedIn|Twitter|Facebook|Bloomberg|ZoomInfo|RocketReach|Glassdoor|Profile).*$",
        "",
        clean_title,
        flags=re.IGNORECASE,
    ).strip()

    if not cleaned:
        return True

    # If role or company words exist, it is not name-only
    if ROLE_OR_COMPANY_KEYWORDS.search(cleaned):
        return False

    # Check word count of remaining cleaned string
    words = cleaned.split()
    return len(words) <= 4


def parse_title_hint(title: str) -> Optional[Dict[str, str]]:
    """
    Parses common 'Name - Title - Company | Site' or 'Name | Title | Company' patterns
    to produce a structured hint for extraction.
    """
    if not title:
        return None

    clean = title.strip()
    # Strip site suffix
    clean = re.sub(
        r"\s*[|–—\-]\s*(LinkedIn|Twitter|Facebook|Bloomberg|ZoomInfo|RocketReach|Glassdoor|Profile).*$",
        "",
        clean,
        flags=re.IGNORECASE,
    ).strip()

    # Try splitting by pipe, dash, en-dash, em-dash
    parts = [p.strip() for p in re.split(r"\s+[|–—-]\s+", clean) if p.strip()]
    if len(parts) >= 3:
        return {
            "name": parts[0],
            "title": parts[1],
            "company": parts[2],
        }
    elif len(parts) == 2:
        sub_m = re.match(r"^(.*?)\s+(?:at|@)\s+(.*)$", parts[1], re.IGNORECASE)
        if sub_m:
            return {
                "name": parts[0],
                "title": sub_m.group(1).strip(),
                "company": sub_m.group(2).strip(),
            }
        return {
            "name": parts[0],
            "title": parts[1],
            "company": "",
        }
    return None


def compute_staleness(published_date: Optional[str], now: Optional[datetime] = None) -> Optional[bool]:
    """
    Computes staleness based on publication date:
    - Returns None if published_date is missing, empty, or unparseable (unknown, not fresh).
    - Returns True if published_date is older than 12 months (> 365 days).
    - Returns False if published_date is within 12 months (<= 365 days).
    """
    if not published_date or not str(published_date).strip():
        return None

    d_str = str(published_date).strip()
    now_dt = now or datetime.now(timezone.utc)

    parsed: Optional[datetime] = None
    try:
        clean_iso = d_str.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(clean_iso)
    except Exception:
        pass

    if parsed is None:
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", d_str)
        if m:
            try:
                parsed = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
            except Exception:
                pass

    if parsed is None:
        m = re.match(r"^(\d{4})$", d_str)
        if m:
            try:
                parsed = datetime(int(m.group(1)), 1, 1, tzinfo=timezone.utc)
            except Exception:
                pass

    if parsed is None:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    diff = now_dt - parsed
    return diff > timedelta(days=365)
