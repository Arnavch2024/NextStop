import hashlib
import re
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from supabase import Client

from app.logger import logger
from app.models.api import ChatResponse


class LLMReplyCache:
    """
    High-performance thread-safe reply cache for Gemini agent loops.
    Minimizes expensive LLM token usage and latency for duplicate or repeated queries.
    Automatically invalidates whenever new data is added to the central data lake
    or database tables (e.g., student imports, recruiter updates, company records).
    """

    def __init__(self, max_capacity: int = 5000, default_ttl_hours: int = 24):
        self.max_capacity = max_capacity
        self.default_ttl_hours = default_ttl_hours
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._lake_version: int = 1
        self._last_invalidation_time: datetime = datetime.now(timezone.utc)
        self._last_invalidation_reason: str = "server_init"
        self._last_db_fingerprint: Optional[str] = None
        self._last_fingerprint_check: datetime = datetime.now(timezone.utc) - timedelta(seconds=60)
        self._stats = {
            "hits": 0,
            "misses": 0,
            "invalidations": 0,
            "saved_gemini_calls": 0,
        }

    def normalize_message(self, message: str) -> str:
        """Normalizes user prompt for consistent caching."""
        if not message:
            return ""
        norm = message.strip().lower()
        norm = re.sub(r"\s+", " ", norm)
        # Remove trailing punctuation like ? or .
        norm = re.sub(r"[?!.,;]+$", "", norm)
        return norm

    def compute_cache_key(
        self,
        message: str,
        role: Optional[str] = None,
        college_id: Optional[str] = None,
        company_id: Optional[str] = None,
        is_demo: bool = False,
    ) -> str:
        """Generates SHA-256 fingerprint for message + role context + demo/real flag + data lake version."""
        norm_msg = self.normalize_message(message)
        r = (role or "student").lower()
        cid = college_id or "none"
        comp_id = company_id or "none"
        demo_str = "demo" if is_demo else "real"
        composite = f"v{self._lake_version}|{demo_str}|{r}|{cid}|{comp_id}|{norm_msg}"
        return hashlib.sha256(composite.encode("utf-8")).hexdigest()

    def get_cached_reply(
        self,
        message: str,
        role: Optional[str] = None,
        college_id: Optional[str] = None,
        company_id: Optional[str] = None,
        is_demo: bool = False,
        client: Optional[Client] = None,
    ) -> Optional[ChatResponse]:
        """
        Retrieves a cached response if valid and unexpired.
        Also inspects database fingerprint periodically to detect out-of-band updates.
        """
        # Periodic check for out-of-band database mutations (e.g. Supabase Dashboard SQL)
        if client:
            self.maybe_sync_database_fingerprint(client)

        cache_key = self.compute_cache_key(message, role, college_id, company_id, is_demo=is_demo)
        now = datetime.now(timezone.utc)

        with self._lock:
            entry = self._cache.get(cache_key)
            if not entry:
                self._stats["misses"] += 1
                return None

            # Check expiration
            expires_at = entry.get("expires_at")
            if expires_at and now > expires_at:
                del self._cache[cache_key]
                self._stats["misses"] += 1
                return None

            self._stats["hits"] += 1
            # Average agent execution makes ~2-3 LLM iterations
            self._stats["saved_gemini_calls"] += 2
            logger.info(
                f"[LLMCache] HIT for key {cache_key[:10]} (role={role}, demo={is_demo}, query='{message[:30]}...'). "
                f"Saved Gemini API calls! Total hits: {self._stats['hits']}"
            )

            try:
                # Reconstruct ChatResponse from cached dictionary
                cached_data = entry["response"]
                return ChatResponse(**cached_data)
            except Exception as e:
                logger.warning(f"[LLMCache] Failed to deserialize cached response: {e}")
                del self._cache[cache_key]
                return None

    def set_cached_reply(
        self,
        message: str,
        role: Optional[str],
        response: ChatResponse,
        college_id: Optional[str] = None,
        company_id: Optional[str] = None,
        is_demo: bool = False,
        ttl_hours: Optional[int] = None,
    ) -> None:
        """
        Caches a ChatResponse.
        Skips caching if the request performed write mutations (records_created is non-empty).
        """
        # Do not cache messages that resulted in database writes (facts stated, profile updates, etc.)
        if response.records_created and len(response.records_created) > 0:
            logger.debug("[LLMCache] Skipping caching: query produced database records_created.")
            return

        ttl = ttl_hours if ttl_hours is not None else self.default_ttl_hours
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=ttl)
        cache_key = self.compute_cache_key(message, role, college_id, company_id, is_demo=is_demo)

        with self._lock:
            # Enforce max capacity using LRU-style oldest eviction
            if len(self._cache) >= self.max_capacity:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]

            self._cache[cache_key] = {
                "response": response.model_dump(mode="json"),
                "query": message,
                "role": role,
                "cached_at": now,
                "expires_at": expires_at,
            }
            logger.info(
                f"[LLMCache] STORED key {cache_key[:10]} (role={role}, TTL={ttl}h). "
                f"Total cached items: {len(self._cache)}"
            )

    def invalidate(self, reason: str = "data_lake_update") -> None:
        """
        Instantly clears the LLM reply cache and increments the lake version.
        Guarantees that following queries will hit fresh data and query Gemini.
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._lake_version += 1
            self._last_invalidation_time = datetime.now(timezone.utc)
            self._last_invalidation_reason = reason
            self._stats["invalidations"] += 1
            logger.info(
                f"[LLMCache] INVALIDATED {count} items due to: '{reason}'. New lake version: {self._lake_version}."
            )

    def maybe_sync_database_fingerprint(self, client: Client, check_interval_seconds: int = 20) -> None:
        """
        Periodically checks database timestamps to invalidate cache if new rows
        were inserted into central lake tables directly outside this process.
        """
        now = datetime.now(timezone.utc)
        if (now - self._last_fingerprint_check).total_seconds() < check_interval_seconds:
            return

        self._last_fingerprint_check = now
        try:
            # Check latest timestamps from contacts and student_records
            latest_contact = (
                client.table("contacts").select("updated_at").order("updated_at", desc=True).limit(1).execute()
            )
            latest_student = (
                client.table("student_records").select("updated_at").order("updated_at", desc=True).limit(1).execute()
            )

            contact_ts = latest_contact.data[0]["updated_at"] if latest_contact.data else ""
            student_ts = latest_student.data[0]["updated_at"] if latest_student.data else ""
            current_fingerprint = f"{contact_ts}:{student_ts}"

            if self._last_db_fingerprint is not None and self._last_db_fingerprint != current_fingerprint:
                self.invalidate(reason=f"database_fingerprint_changed: {current_fingerprint[:20]}")

            self._last_db_fingerprint = current_fingerprint
        except Exception as e:
            logger.debug(f"[LLMCache] Fingerprint check skipped: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Returns live cache diagnostics and savings metrics."""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0.0
            return {
                "cached_entries": len(self._cache),
                "lake_version": self._lake_version,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate_percent": round(hit_rate, 2),
                "saved_gemini_api_calls": self._stats["saved_gemini_calls"],
                "last_invalidation_time": self._last_invalidation_time.isoformat(),
                "last_invalidation_reason": self._last_invalidation_reason,
            }


# Global singleton instance
llm_reply_cache = LLMReplyCache()


def get_llm_reply_cache() -> LLMReplyCache:
    return llm_reply_cache


def invalidate_llm_cache(reason: str = "central_lake_mutation") -> None:
    """Convenience helper to clear LLM reply cache from anywhere in the codebase."""
    llm_reply_cache.invalidate(reason=reason)
