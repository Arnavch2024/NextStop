import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from supabase import Client

from app.logger import logger

# Local file/memory fallback cache if Supabase search_cache table is missing
_LOCAL_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache"
_LOCAL_CACHE_FILE = _LOCAL_CACHE_DIR / "search_cache.json"
_MEMORY_SEARCH_CACHE: Dict[str, Dict[str, Any]] = {}

_EXTRACTION_CACHE_FILE = _LOCAL_CACHE_DIR / "extraction_cache.json"
_MEMORY_EXTRACTION_CACHE: Dict[str, List[Dict[str, Any]]] = {}

# Provider options version: invalidates cache when settings (such as highlights) change
PROVIDER_OPTIONS_VERSION = "v2_exa_highlights"


def clear_local_search_cache() -> None:
    """Clears local disk and memory caches to force fresh retrieval."""
    global _MEMORY_SEARCH_CACHE, _MEMORY_EXTRACTION_CACHE
    _MEMORY_SEARCH_CACHE = {}
    _MEMORY_EXTRACTION_CACHE = {}
    try:
        if _LOCAL_CACHE_FILE.exists():
            _LOCAL_CACHE_FILE.unlink()
        if _EXTRACTION_CACHE_FILE.exists():
            _EXTRACTION_CACHE_FILE.unlink()
    except Exception as e:
        logger.debug(f"Could not remove local cache files: {e}")


def get_cached_extraction(cache_key: str) -> Optional[List[Dict[str, Any]]]:
    """Retrieves cached structured LLM extraction for candidate contacts."""
    global _MEMORY_EXTRACTION_CACHE
    if not _MEMORY_EXTRACTION_CACHE and _EXTRACTION_CACHE_FILE.exists():
        try:
            with open(_EXTRACTION_CACHE_FILE, "r", encoding="utf-8") as f:
                _MEMORY_EXTRACTION_CACHE = json.load(f)
        except Exception:
            pass
    return _MEMORY_EXTRACTION_CACHE.get(cache_key)


def write_cached_extraction(cache_key: str, contacts: List[Dict[str, Any]]) -> None:
    """Caches structured LLM extraction for candidate contacts."""
    global _MEMORY_EXTRACTION_CACHE
    _MEMORY_EXTRACTION_CACHE[cache_key] = contacts
    try:
        _LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_EXTRACTION_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_MEMORY_EXTRACTION_CACHE, f)
    except Exception:
        pass


def _load_local_cache() -> None:
    global _MEMORY_SEARCH_CACHE
    if not _MEMORY_SEARCH_CACHE and _LOCAL_CACHE_FILE.exists():
        try:
            with open(_LOCAL_CACHE_FILE, "r", encoding="utf-8") as f:
                _MEMORY_SEARCH_CACHE = json.load(f)
        except Exception:
            pass


def _save_local_cache() -> None:
    try:
        _LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_LOCAL_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_MEMORY_SEARCH_CACHE, f)
    except Exception:
        pass


def normalize_query(query: str) -> str:
    """Normalizes query text: lowercase, strip, collapsed spaces, alphanumeric-focused."""
    if not query:
        return ""
    q = query.strip().lower()
    q = re.sub(r"\s+", " ", q)
    return q


def compute_query_hash(
    query: str,
    purpose: Optional[str] = None,
    options_version: Optional[str] = None,
) -> str:
    """Generates sha256 hash of normalized query + purpose + provider options version."""
    norm = normalize_query(query)
    purp = (purpose or "").strip().lower()
    opt_ver = options_version if options_version is not None else PROVIDER_OPTIONS_VERSION
    combined = f"{norm}|{purp}|{opt_ver}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def get_cached_search(
    client: Client,
    query: str,
    purpose: Optional[str] = None,
    options_version: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Checks search_cache for an unexpired result.
    Returns cached result dict or None.
    """
    q_hash = compute_query_hash(query, purpose, options_version=options_version)
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        res = (
            client.table("search_cache")
            .select("query_hash, provider, result, expires_at")
            .eq("query_hash", q_hash)
            .gte("expires_at", now_iso)
            .execute()
        )
        if res.data and len(res.data) > 0:
            row = res.data[0]
            logger.info(f"search_cache HIT for hash {q_hash[:10]}")
            return {
                "provider": row.get("provider", "cache"),
                "results": row.get("result", []),
                "cached": True,
            }
        return None
    except Exception as e:
        logger.debug(f"search_cache table lookup: {e}")

    # Fallback to local memory/disk cache only when table is missing
    _load_local_cache()
    if q_hash in _MEMORY_SEARCH_CACHE:
        entry = _MEMORY_SEARCH_CACHE[q_hash]
        if entry.get("expires_at", "") >= now_iso:
            logger.info(f"local search_cache HIT for hash {q_hash[:10]}")
            return {
                "provider": entry.get("provider", "cache"),
                "results": entry.get("result", []),
                "cached": True,
            }

    return None


def write_search_cache(
    client: Client,
    query: str,
    provider: str,
    purpose: Optional[str],
    results: Any,
    ttl_days: int = 7,
    options_version: Optional[str] = None,
) -> None:
    """Writes an enriched search result to search_cache with TTL."""
    q_hash = compute_query_hash(query, purpose, options_version=options_version)
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(days=ttl_days)).isoformat()

    cache_row = {
        "query_hash": q_hash,
        "query": normalize_query(query),
        "provider": provider,
        "purpose": purpose,
        "result": results,
        "expires_at": expires_at,
    }

    try:
        # Check if already exists to update or insert
        existing = client.table("search_cache").select("id").eq("query_hash", q_hash).execute()
        if existing.data and len(existing.data) > 0:
            client.table("search_cache").update(cache_row).eq("query_hash", q_hash).execute()
        else:
            client.table("search_cache").insert(cache_row).execute()
        logger.info(f"search_cache written for hash {q_hash[:10]} (TTL {ttl_days}d)")
        return
    except Exception as e:
        logger.debug(f"search_cache remote table write skipped ({e}), storing locally.")

    # Persist locally only when remote table is unavailable
    _load_local_cache()
    _MEMORY_SEARCH_CACHE[q_hash] = cache_row
    _save_local_cache()
