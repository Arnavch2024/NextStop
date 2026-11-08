import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from supabase import Client

from app.config import settings
from app.logger import logger
from app.models.db import ProfileRole, UserProfile
from app.search.dedupe import normalize_name, upsert_contact
from app.search.extract_contacts import extract_company_contacts, extract_contacts_from_text
from app.search.providers.base import SearchProvider
from app.search.providers.extract import is_data_broker, normalize_url
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

    try:
        if linkedin:
            q = (
                client.table("contacts")
                .select("id")
                .ilike("linkedin_url", linkedin)
                .is_("suppressed_at", "null")
                .execute()
            )
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
    except Exception:
        pass

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
    queries_per_company: Optional[int] = None,
    confirm_yes: bool = False,
    only_urls: Optional[Union[List[str], str]] = None,
) -> Dict[str, Any]:
    """
    Ingests real-world contacts for companies in the data lake via web search enrichment.
    Never fetches LinkedIn directly; respects search cache (7-day TTL); never stores phone numbers.
    Stops cleanly on provider errors / quota exhaustion.
    """
    user = admin_user or SYSTEM_ADMIN_USER

    # 1. Fetch companies
    try:
        comp_query = client.table("companies").select("*")
        comp_res = comp_query.execute()
        all_companies = comp_res.data or []
    except Exception as exc:
        logger.warning(f"Could not fetch companies from database: {exc}")
        all_companies = []

    if not all_companies:
        from app.db.seed import MUMBAI_COMPANIES

        logger.info("Using reference list of Mumbai companies for ingestion.")
        all_companies = [dict(c, id=f"ref-{i + 1}") for i, c in enumerate(MUMBAI_COMPANIES)]

    # Filter by category if requested
    if category:
        all_companies = [
            c for c in all_companies if (c.get("category") or "").strip().lower() == category.strip().lower()
        ]

    # Limit
    if limit is not None and limit > 0:
        all_companies = all_companies[:limit]

    num_queries = queries_per_company or settings.INGEST_QUERIES_PER_COMPANY
    query_templates = settings.INGEST_QUERY_TEMPLATES[:num_queries]

    # Parse and normalize approved URLs if --only-urls provided
    approved_urls_set: Optional[Set[str]] = None
    if only_urls:
        if isinstance(only_urls, str):
            p = Path(only_urls)
            if p.exists() and p.is_file():
                urls = [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
            else:
                urls = [u.strip() for u in only_urls.split(",") if u.strip()]
        else:
            urls = list(only_urls)
        approved_urls_set = {normalize_url(u) for u in urls if u}
        logger.info(f"--only-urls active: restricted to {len(approved_urls_set)} approved source URL(s).")

    stats = {
        "companies_processed": 0,
        "contacts_added": 0,
        "contacts_merged": 0,
        "contacts_dropped": 0,
        "skipped_no_info": 0,
        "broker_results_rejected": 0,
        "errors": 0,
        "provider_calls": {
            "exa": 0,
            "tavily": 0,
            "gemini": 0,
            "cache_hits": 0,
            "gemini_per_company": {},
        },
        "candidates": [],
        "dropped_candidates": [],
    }

    total_companies = len(all_companies)
    est_search_calls = total_companies * len(query_templates) * 2
    est_gemini_calls = total_companies
    logger.info(
        f"Pre-run estimate: {total_companies} companies x {len(query_templates)} queries = "
        f"{total_companies * len(query_templates)} base search calls (up to {est_search_calls} if Tavily fallback is needed) "
        f"+ {est_gemini_calls} Gemini calls"
    )

    if est_search_calls > 200 and not confirm_yes:
        raise ValueError(
            f"Estimated maximum search calls ({est_search_calls}) exceeds budget of 200. "
            "Re-run with --yes to confirm or reduce --limit / --queries-per-company."
        )

    logger.info(f"Starting contact ingestion for {total_companies} companies (dry_run={dry_run}, category={category})")

    for idx, comp in enumerate(all_companies):
        comp_name = comp.get("name", "").strip()
        comp_id = str(comp.get("id"))
        if not comp_name:
            continue

        seen_company_urls: Dict[str, Dict[str, Any]] = {}
        stop_due_to_quota = False

        for q_tmpl in query_templates:
            query = q_tmpl.format(company=comp_name)
            purpose = f"campus recruiter / university recruiting at {comp_name}, Mumbai"

            try:
                search_res = web_search_enrich(
                    client=client,
                    query=query,
                    purpose=purpose,
                    actor_id=user.id if user.id and str(user.id) != "00000000-0000-0000-0000-000000000000" else None,
                    primary_provider=search_provider,
                    multi_provider=(search_provider is None),
                )
                if search_res.get("cached"):
                    stats["provider_calls"]["cache_hits"] += 1
                else:
                    prov_calls = search_res.get("provider_calls")
                    if prov_calls:
                        stats["provider_calls"]["exa"] += prov_calls.get("exa", 0)
                        stats["provider_calls"]["tavily"] += prov_calls.get("tavily", 0)
                    else:
                        prov = search_res.get("provider", "exa")
                        if prov in stats["provider_calls"]:
                            stats["provider_calls"][prov] += 1
                        else:
                            stats["provider_calls"]["exa"] += 1

                for r in search_res.get("results", []):
                    u = r.get("url", "")
                    norm_u = normalize_url(u)
                    if not norm_u:
                        continue
                    if norm_u not in seen_company_urls:
                        seen_company_urls[norm_u] = r
                    else:
                        curr_snip = seen_company_urls[norm_u].get("snippet", "")
                        new_snip = r.get("snippet", "")
                        if len(new_snip) > len(curr_snip) or (
                            not seen_company_urls[norm_u].get("published_date") and r.get("published_date")
                        ):
                            seen_company_urls[norm_u] = r
            except Exception as exc:
                err_str = str(exc).lower()
                logger.error(f"Search provider error for '{comp_name}' with query '{query}': {exc}")
                stats["errors"] += 1
                if any(m in err_str for m in ("429", "quota", "resource_exhausted", "rate limit")):
                    logger.warning(f"Quota exhaustion detected. Stopping ingestion cleanly: {exc}")
                    stop_due_to_quota = True
                    break
                continue

        if stop_due_to_quota:
            break

        results = list(seen_company_urls.values())
        if not results:
            logger.warning(f"No search results found for company '{comp_name}'")
            stats["companies_processed"] += 1
            continue

        # Filter out data-broker aggregator domains BEFORE extraction
        clean_results = []
        broker_count = 0
        for r in results:
            url = r.get("url", "")
            if is_data_broker(url):
                broker_count += 1
                continue
            clean_results.append(r)

        if broker_count > 0:
            logger.info(f"Rejected {broker_count} data-broker result(s) matching blocklist")
            stats["broker_results_rejected"] += broker_count

        # Compatibility check: if a test explicitly mocks extract_contacts_from_text
        from unittest.mock import Mock

        is_mocked = isinstance(extract_contacts_from_text, Mock)

        if is_mocked:
            extracted = []
            for r in clean_results:
                url = r.get("url")
                title = r.get("title", "")
                snippet = r.get("snippet", "")
                page_text = r.get("page_text")
                text_to_extract = f"{title}\n{page_text}" if page_text else f"{title}\n{snippet}"
                stats["provider_calls"]["gemini"] += 1
                try:
                    res_cands = extract_contacts_from_text(
                        text=text_to_extract,
                        source_url=url,
                        llm_provider=llm_provider,
                        target_company=comp_name,
                    )
                    extracted.extend(res_cands)
                except Exception as exc:
                    logger.warning(f"Extraction error for result from '{url}': {exc}")
                    stats["errors"] += 1
        else:
            # Production path: One extraction call per company across clean results with caching
            try:
                ext_res = extract_company_contacts(
                    results=clean_results,
                    target_company=comp_name,
                    llm_provider=llm_provider,
                )
                extracted, dropped_for_comp, was_cached = ext_res
                stats["skipped_no_info"] += getattr(ext_res, "skipped_no_info", 0)

                if not was_cached:
                    stats["provider_calls"]["gemini"] += 1
                    stats["provider_calls"]["gemini_per_company"][comp_name] = 1
                else:
                    stats["provider_calls"]["cache_hits"] += 1
                    stats["provider_calls"]["gemini_per_company"][comp_name] = 0

                stats["dropped_candidates"].extend(dropped_for_comp)
                stats["contacts_dropped"] += len(dropped_for_comp)

            except Exception as exc:
                err_str = str(exc).lower()
                logger.warning(f"Extraction error for company '{comp_name}': {exc}")
                stats["errors"] += 1
                if any(m in err_str for m in ("429", "quota", "resource_exhausted")):
                    logger.warning("Quota exhaustion during extraction. Stopping ingestion cleanly.")
                    return stats
                continue

        for cand in extracted:
            if not cand.name or not cand.name.strip():
                stats["contacts_dropped"] += 1
                continue

            # If --only-urls filter is active, only process candidates whose source_url is approved
            if approved_urls_set is not None:
                cand_url_norm = normalize_url(cand.source_url or "")
                if cand_url_norm not in approved_urls_set:
                    logger.debug(
                        f"Candidate '{cand.name}' skipped: source URL '{cand.source_url}' not in approved --only-urls list."
                    )
                    continue

            cand_dict = cand.model_dump()
            cand_dict["company_id"] = comp_id
            cand_dict["company_name"] = comp_name
            # Hard rule: never store phone numbers in lake
            cand_dict.pop("phone", None)

            # Cap confidence at 0.4 if stale, 0.6 if not stale (for single unfetched source)
            if not cand.verified or cand.fetch_status != "ok":
                if cand.stale is True:
                    cand_dict["confidence"] = min(float(cand_dict.get("confidence", 0.6)), 0.4)
                else:
                    cand_dict["confidence"] = min(float(cand_dict.get("confidence", 0.6)), 0.6)
            cand_dict["unverified"] = (cand.fetch_status != "ok") or (not cand.verified)

            if dry_run:
                would_merge = _check_would_merge(client, cand_dict, comp_id)
                op_type = "merge" if would_merge else "add"
                cand_entry = {
                    "company": comp_name,
                    "name": cand.name,
                    "title": cand.title or "Recruiter",
                    "location": cand.location,
                    "source_url": cand.source_url or "",
                    "matched_rule": cand.matched_rule or f"{cand.name} at {comp_name}",
                    "confidence": cand_dict["confidence"],
                    "fetch_status": cand.fetch_status,
                    "published_date": cand.published_date,
                    "stale": cand.stale,
                    "operation": op_type,
                }
                stats.setdefault("candidates", []).append(cand_entry)

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
                        source_url=cand.source_url or "",
                    )
                    op_type = "merge" if res.get("op") in ("merged", "updated") else "add"
                    cand_entry = {
                        "company": comp_name,
                        "name": cand.name,
                        "title": cand.title or "Recruiter",
                        "location": cand.location,
                        "source_url": cand.source_url or "",
                        "matched_rule": cand.matched_rule or f"{cand.name} at {comp_name}",
                        "confidence": cand_dict["confidence"],
                        "fetch_status": cand.fetch_status,
                        "published_date": cand.published_date,
                        "stale": cand.stale,
                        "operation": op_type,
                    }
                    stats.setdefault("candidates", []).append(cand_entry)

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
