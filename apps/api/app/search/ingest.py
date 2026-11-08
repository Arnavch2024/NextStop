import time
from typing import Any, Dict, Optional

from supabase import Client

from app.logger import logger
from app.models.db import ProfileRole, UserProfile
from app.search.dedupe import normalize_name, upsert_contact
from app.search.extract_contacts import extract_contacts_from_text
from app.search.providers.base import SearchProvider
from app.search.web import web_search_enrich

SYSTEM_ADMIN_USER = UserProfile(
    id="00000000-0000-0000-0000-000000000000",
    role=ProfileRole.RECRUITER,
    display_name="System Ingest",
    email="admin@nextstop.local",
)


def _check_would_merge(client: Client, candidate: Dict[str, Any], company_id: str) -> bool:
    """Simulates match check against shared contacts lake for dry-run."""
    linkedin = candidate.get("linkedin_url", "").strip().lower() if candidate.get("linkedin_url") else None
    email = candidate.get("email", "").strip().lower() if candidate.get("email") else None
    name = candidate.get("name", "").strip()

    if linkedin:
        q = client.table("contacts").select("id").ilike("linkedin_url", linkedin).is_("suppressed_at", "null").execute()
        if q.data and len(q.data) > 0:
            return True

    if email:
        q = client.table("contacts").select("id").ilike("email", email).is_("suppressed_at", "null").execute()
        if q.data and len(q.data) > 0:
            return True

    if name and company_id:
        q = (
            client.table("contacts")
            .select("id, name")
            .eq("company_id", company_id)
            .is_("suppressed_at", "null")
            .execute()
        )
        for cand in q.data or []:
            if normalize_name(cand.get("name", "")) == normalize_name(name):
                return True

    return False


def run_ingest(
    client: Client,
    category: Optional[str] = None,
    limit: Optional[int] = None,
    delay: float = 1.0,
    dry_run: bool = False,
    search_provider: Optional[SearchProvider] = None,
    llm_provider: Optional[Any] = None,
    admin_user: Optional[UserProfile] = None,
) -> Dict[str, int]:
    """
    Ingests real-world contacts for companies in the data lake via web search enrichment.
    Never fetches LinkedIn directly; respects search cache (7-day TTL); never stores phone numbers.
    Stops cleanly on provider errors / quota exhaustion.
    """
    user = admin_user or SYSTEM_ADMIN_USER

    # 1. Fetch companies
    comp_query = client.table("companies").select("*")
    comp_res = comp_query.execute()
    all_companies = comp_res.data or []

    # Filter by category if requested
    if category:
        all_companies = [
            c for c in all_companies if (c.get("category") or "").strip().lower() == category.strip().lower()
        ]

    # Limit
    if limit is not None and limit > 0:
        all_companies = all_companies[:limit]

    stats = {
        "companies_processed": 0,
        "contacts_added": 0,
        "contacts_merged": 0,
        "contacts_dropped": 0,
        "errors": 0,
    }

    total_companies = len(all_companies)
    logger.info(f"Starting contact ingestion for {total_companies} companies (dry_run={dry_run}, category={category})")

    for idx, comp in enumerate(all_companies):
        comp_name = comp.get("name", "").strip()
        comp_id = str(comp.get("id"))
        if not comp_name:
            continue

        query = f"{comp_name} campus recruiter university recruiting Mumbai"
        purpose = f"campus recruiter / university recruiting at {comp_name}, Mumbai"

        try:
            search_res = web_search_enrich(
                client=client,
                query=query,
                purpose=purpose,
                actor_id=user.id,
                primary_provider=search_provider,
            )
        except Exception as exc:
            err_str = str(exc).lower()
            logger.error(f"Search provider error for '{comp_name}': {exc}")
            stats["errors"] += 1
            # Quota or rate limit error: stop cleanly
            if any(m in err_str for m in ("429", "quota", "resource_exhausted", "rate limit")):
                logger.warning(f"Quota exhaustion detected. Stopping ingestion cleanly: {exc}")
                break
            continue

        if search_res.get("provider") == "failed":
            logger.warning(f"Search failed for company '{comp_name}'")
            stats["errors"] += 1
            continue

        results = search_res.get("results", [])

        # Process search results for contacts
        for r in results:
            url = r.get("url")
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            page_text = r.get("page_text")

            # LinkedIn is never fetched; uses title + snippet from public search result
            text_to_extract = f"{title}\n{page_text}" if page_text else f"{title}\n{snippet}"

            try:
                extracted = extract_contacts_from_text(
                    text=text_to_extract,
                    source_url=url,
                    llm_provider=llm_provider,
                )
            except Exception as exc:
                err_str = str(exc).lower()
                logger.warning(f"Extraction error for result from '{url}': {exc}")
                stats["errors"] += 1
                if any(m in err_str for m in ("429", "quota", "resource_exhausted")):
                    logger.warning("Quota exhaustion during extraction. Stopping ingestion cleanly.")
                    return stats
                continue

            for cand in extracted:
                if not cand.name or not cand.name.strip():
                    stats["contacts_dropped"] += 1
                    continue

                cand_dict = cand.model_dump()
                cand_dict["company_id"] = comp_id
                cand_dict["company_name"] = comp_name
                # Hard rule: never store phone numbers in lake
                cand_dict.pop("phone", None)

                if dry_run:
                    would_merge = _check_would_merge(client, cand_dict, comp_id)
                    if would_merge:
                        stats["contacts_merged"] += 1
                        logger.info(f"[DRY-RUN WOULD MERGE] {cand.name} ({cand.title}) at {comp_name}")
                    else:
                        stats["contacts_added"] += 1
                        logger.info(f"[DRY-RUN WOULD ADD] {cand.name} ({cand.title}) at {comp_name}")
                else:
                    try:
                        res = upsert_contact(
                            client=client,
                            candidate=cand_dict,
                            user=user,
                            source="web",
                            source_url=cand.source_url or url,
                        )
                        if res.get("error") == "nameless_candidate":
                            stats["contacts_dropped"] += 1
                        elif res.get("op") == "created":
                            stats["contacts_added"] += 1
                            logger.info(f"[ADDED] {cand.name} ({cand.title}) at {comp_name}")
                        elif res.get("op") in ("merged", "updated"):
                            stats["contacts_merged"] += 1
                            logger.info(f"[MERGED] {cand.name} ({cand.title}) at {comp_name}")
                    except Exception as exc:
                        logger.error(f"Failed to upsert contact '{cand.name}': {exc}")
                        stats["errors"] += 1

        stats["companies_processed"] += 1

        # Rate-limiting delay between companies
        if delay > 0 and idx < total_companies - 1:
            time.sleep(delay)

    return stats
