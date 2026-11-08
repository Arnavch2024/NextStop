import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from supabase import Client

from app.logger import logger


def normalize_query(query: str) -> str:
    """Normalizes query text: lowercase, strip, collapsed spaces, alphanumeric-focused."""
    if not query:
        return ""
    q = query.strip().lower()
    q = re.sub(r"\s+", " ", q)
    return q


def compute_query_hash(query: str, purpose: Optional[str] = None) -> str:
    """Generates sha256 hash of normalized query + purpose."""
    norm = normalize_query(query)
    purp = (purpose or "").strip().lower()
    combined = f"{norm}|{purp}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def get_cached_search(
    client: Client,
    query: str,
    purpose: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Checks search_cache for an unexpired result.
    Returns cached result dict or None.
    """
    q_hash = compute_query_hash(query, purpose)
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
    except Exception as e:
        logger.warning(f"Error reading search_cache: {e}")

    return None


def write_search_cache(
    client: Client,
    query: str,
    provider: str,
    purpose: Optional[str],
    results: Any,
    ttl_days: int = 7,
) -> None:
    """Writes an enriched search result to search_cache with TTL."""
    q_hash = compute_query_hash(query, purpose)
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
    except Exception as e:
        logger.warning(f"Error writing search_cache: {e}")
