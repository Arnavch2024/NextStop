from typing import Any, Dict, List, Optional

from supabase import Client

from app.config import settings
from app.db.supabase import write_raw_event
from app.logger import logger
from app.search.cache import get_cached_search, write_search_cache
from app.search.extract_contacts import extract_company_contacts
from app.search.providers.base import ProviderError, SearchProvider
from app.search.providers.exa import ExaSearchProvider
from app.search.providers.extract import (
    WEB_CONTENT_PROMPT_RULE,
    fetch_page_text,
    is_data_broker,
    is_linkedin,
    is_name_only_empty_snippet,
    normalize_url,
    robots_allows,
)
from app.search.providers.tavily import TavilySearchProvider


def format_web_content_block(search_results: List[Dict[str, Any]]) -> str:
    """Wraps search results securely inside a delimited <web_content> block."""
    items_text = []
    for i, r in enumerate(search_results, 1):
        url = r.get("url", "")
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        page_text = r.get("page_text")
        body = page_text if page_text else snippet
        items_text.append(f"Result [{i}]:\nTitle: {title}\nURL: {url}\nContent: {body}\n")

    combined = "\n---\n".join(items_text)
    return f"{WEB_CONTENT_PROMPT_RULE}\n\n<web_content>\n{combined}\n</web_content>"


def _run_extraction_pipeline_and_return_clean(
    client: Client,
    enriched: List[Dict[str, Any]],
    broker_rejected_count: int,
    actor_id: Optional[str] = None,
    llm_provider: Optional[Any] = None,
    user: Optional[Any] = None,
    target_company: Optional[str] = None,
) -> Dict[str, Any]:
    """Runs the precision extraction and ingestion pipeline on web search results.

    Returns ONLY accepted contacts with lake IDs and counts. Never returns raw snippets or highlights.
    """
    from app.models.db import UserProfile
    from app.search.dedupe import upsert_contact
    from app.search.ingest import SYSTEM_ADMIN_USER, get_or_create_company

    clean_results = [
        r
        for r in enriched
        if not is_data_broker(r.get("url", ""))
        and not is_name_only_empty_snippet(r.get("title", ""), r.get("snippet", ""), r.get("page_text"))
    ]

    from app.search.providers.extract import parse_title_hint

    hint_comp = None
    for r in clean_results:
        h = parse_title_hint(r.get("title", ""))
        if h and h.get("company"):
            hint_comp = h["company"]
            break

    target = target_company or (clean_results[0].get("company") if clean_results else None) or hint_comp or ""

    try:
        ext_res = extract_company_contacts(
            results=clean_results,
            target_company=target,
            llm_provider=llm_provider,
        )
        extracted_cands, dropped_cands, _ = ext_res
    except Exception as exc:
        logger.warning(f"Precision extraction error: {exc}")
        extracted_cands, dropped_cands = [], []

    accepted_contacts: List[Dict[str, Any]] = []
    admin_user = user or (UserProfile(id=actor_id, role="student") if actor_id else SYSTEM_ADMIN_USER)

    for cand in extracted_cands:
        comp_id = None
        if cand.company:
            comp_id = get_or_create_company(client, cand.company, user_id=actor_id)

        cand_row = {
            "name": cand.name,
            "title": cand.title,
            "company_id": comp_id,
            "company_name": cand.company,
            "college_id": None,
            "role_type": cand.role_type or "campus_recruiter",
            "linkedin_url": cand.linkedin_url or (cand.source_url if is_linkedin(cand.source_url) else None),
            "email": cand.email,
            "location": cand.location,
            "source": "web",
            "source_url": cand.source_url,
            "source_published_date": cand.published_date,
            "stale": cand.stale,
            "confidence": cand.confidence,
            "unverified": True,
            "fetch_status": cand.fetch_status,
        }

        upsert_res = upsert_contact(
            client=client,
            candidate=cand_row,
            user=admin_user,
            source="web",
            source_url=cand.source_url,
        )

        accepted_contacts.append(
            {
                "id": upsert_res["contact_id"],
                "name": cand.name,
                "title": cand.title,
                "company_id": comp_id,
                "company_name": cand.company,
                "location": cand.location,
                "source": "web",
                "source_url": cand.source_url,
                "source_published_date": cand.published_date,
                "stale": cand.stale,
                "confidence": cand.confidence,
                "unverified": True,
            }
        )

    return {
        "results": len(clean_results),
        "accepted": len(accepted_contacts),
        "dropped": len(dropped_cands),
        "broker_rejected": broker_rejected_count,
        "contacts": accepted_contacts,
    }


def web_search_enrich(
    client: Client,
    query: str,
    purpose: Optional[str] = None,
    actor_id: Optional[str] = None,
    primary_provider: Optional[SearchProvider] = None,
    fallback_provider: Optional[SearchProvider] = None,
    num_results: int = 10,
    multi_provider: bool = False,
    providers: Optional[List[SearchProvider]] = None,
    options_version: Optional[str] = None,
    min_usable_results: Optional[int] = None,
    extract_and_ingest: bool = False,
    llm_provider: Optional[Any] = None,
    user: Optional[Any] = None,
    target_company: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Provider-agnostic web search with 7-day TTL cache and safe extraction guards.
    1. Checks search_cache for normalized query.
    2. Runs Exa; calls Tavily only if Exa fails or returns fewer than min_usable_results (default 3).
    3. Guards: LinkedIn pages are never fetched (link-only); robots.txt respected.
    4. Caches enriched result.
    5. Logs raw_events row (source='search').
    6. If extract_and_ingest=True, runs the full ingestion pipeline inside the tool and returns
       ONLY accepted contacts with lake IDs, plus counts. Raw snippets/text are never returned.
    """
    clean_query = query.strip()
    if not clean_query:
        if extract_and_ingest:
            return {"results": 0, "accepted": 0, "dropped": 0, "broker_rejected": 0, "contacts": []}
        return {"provider": "none", "results": [], "cached": False}

    # 1. Check Cache
    cached = get_cached_search(client, clean_query, purpose, options_version=options_version)
    if cached:
        if not extract_and_ingest:
            return cached
        enriched = cached.get("results", [])
        broker_rejected_count = sum(1 for r in enriched if is_data_broker(r.get("url", "")))
        return _run_extraction_pipeline_and_return_clean(
            client=client,
            enriched=enriched,
            broker_rejected_count=broker_rejected_count,
            actor_id=actor_id,
            llm_provider=llm_provider,
            user=user,
            target_company=target_company,
        )

    provider_calls = {"exa": 0, "tavily": 0}
    threshold = (
        min_usable_results if min_usable_results is not None else getattr(settings, "TAVILY_FALLBACK_MIN_RESULTS", 3)
    )

    # 2. Providers Execution
    if multi_provider or providers is not None:
        search_provs = providers or [
            primary_provider or ExaSearchProvider(),
            fallback_provider or TavilySearchProvider(),
        ]
        seen_urls: Dict[str, Dict[str, Any]] = {}
        successful_provs = []
        exa_usable_count = 0

        for i, prov in enumerate(search_provs):
            p_name = (
                "exa"
                if "exa" in prov.__class__.__name__.lower()
                else ("tavily" if "tavily" in prov.__class__.__name__.lower() else f"prov_{i}")
            )

            # Conditional budget guard: If primary (Exa) already returned >= min_usable_results, skip Tavily
            if i > 0 and exa_usable_count >= threshold:
                logger.debug(
                    f"Exa returned {exa_usable_count} usable results (>= threshold {threshold}). Skipping {prov.__class__.__name__}."
                )
                continue

            try:
                res = prov.search(clean_query, num_results=num_results)
                if p_name in provider_calls:
                    provider_calls[p_name] += 1
                successful_provs.append(p_name)
                for r in res:
                    item = r.model_dump() if hasattr(r, "model_dump") else dict(r)
                    url = item.get("url", "")
                    norm_u = normalize_url(url)
                    if not norm_u:
                        continue

                    # Check usability (not data broker, not name-only empty snippet)
                    is_usable = not is_data_broker(url) and not is_name_only_empty_snippet(
                        item.get("title", ""), item.get("snippet", ""), item.get("page_text")
                    )
                    if i == 0 and is_usable:
                        exa_usable_count += 1

                    if norm_u not in seen_urls:
                        seen_urls[norm_u] = item
                    else:
                        # Dedupe: keep richer snippet or entry with published_date
                        curr_item = seen_urls[norm_u]
                        curr_snip = curr_item.get("snippet", "")
                        new_snip = item.get("snippet", "")
                        if len(new_snip) > len(curr_snip) or (
                            not curr_item.get("published_date") and item.get("published_date")
                        ):
                            seen_urls[norm_u] = item
            except ProviderError as e:
                logger.warning(f"Search provider ({prov.__class__.__name__}) error for '{clean_query}': {e}")
                err_str = str(e).lower()
                if any(m in err_str for m in ("429", "quota", "resource_exhausted")):
                    raise

        raw_results = list(seen_urls.values())
        provider_name = "+".join(successful_provs) if successful_provs else "failed"

    else:
        # Fallback flow
        primary = primary_provider or ExaSearchProvider()
        fallback = fallback_provider or TavilySearchProvider()

        raw_results = []
        provider_name = "exa"

        try:
            raw_results = primary.search(clean_query, num_results=num_results)
            provider_name = "exa"
            provider_calls["exa"] = 1
        except ProviderError as e:
            logger.warning(f"Primary search provider ({provider_name}) failed: {e}. Trying fallback...")
            try:
                raw_results = fallback.search(clean_query, num_results=num_results)
                provider_name = "tavily"
                provider_calls["tavily"] = 1
            except ProviderError as e2:
                logger.error(f"Fallback search provider (tavily) also failed: {e2}")
                raw_results = []
                provider_name = "failed"

    # 3. Enrich results: Respect robots.txt, Never fetch LinkedIn
    enriched: List[Dict[str, Any]] = []
    for r in raw_results:
        item = r.model_dump() if hasattr(r, "model_dump") else dict(r)
        url = item.get("url", "")

        if is_linkedin(url):
            # Strict rule: LinkedIn is link-only, never fetched
            item["page_text"] = None
            item["linkedin"] = True
            item["fetch_status"] = "not_fetched"
            enriched.append(item)
            continue

        item["linkedin"] = False
        if robots_allows(url):
            page_text = fetch_page_text(url)
            if page_text:
                item["page_text"] = page_text
                item["fetch_status"] = "ok"
            else:
                item["page_text"] = None
                item["fetch_status"] = "blocked"
        else:
            # Robots disallowed
            item["page_text"] = None
            item["robots_disallowed"] = True
            item["fetch_status"] = "blocked"

        enriched.append(item)

    # 4. Write to search_cache
    ttl_days = settings.SEARCH_CACHE_TTL_DAYS
    write_search_cache(
        client,
        clean_query,
        provider_name,
        purpose,
        enriched,
        ttl_days=ttl_days,
        options_version=options_version,
    )

    # 5. Write audit raw_events
    if actor_id:
        try:
            write_raw_event(
                actor_id,
                source="search",
                payload={
                    "kind": "web",
                    "query": clean_query,
                    "provider": provider_name,
                    "found": len(enriched),
                    "purpose": purpose,
                },
                client=client,
            )
        except Exception as e:
            logger.warning(f"Could not write web search raw_event: {e}")

    if extract_and_ingest:
        broker_rejected_count = sum(1 for r in enriched if is_data_broker(r.get("url", "")))
        return _run_extraction_pipeline_and_return_clean(
            client=client,
            enriched=enriched,
            broker_rejected_count=broker_rejected_count,
            actor_id=actor_id,
            llm_provider=llm_provider,
            user=user,
            target_company=target_company,
        )

    return {
        "provider": provider_name,
        "results": enriched,
        "cached": False,
        "provider_calls": provider_calls,
    }
