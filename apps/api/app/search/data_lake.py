import os
from typing import Any, Dict, List, Optional

from supabase import Client

from app.config import settings
from app.db.supabase import write_raw_event
from app.logger import logger


def _hydrate_contacts_metadata(client: Client, contacts: List[Dict[str, Any]]) -> None:
    """If contacts lack location/source_url/confidence/unverified (e.g. unmigrated contacts table),
    hydrates them from contact_metadata raw_events."""
    need_hydration = [c for c in contacts if c.get("source_url") is None and c.get("location") is None]
    if not need_hydration:
        return
    c_ids = {str(c["id"]) for c in need_hydration if c.get("id")}
    try:
        events_res = (
            client.table("raw_events")
            .select("payload, created_at")
            .eq("source", "contact_metadata")
            .order("created_at", desc=False)
            .execute()
        )
        meta_by_id = {}
        for ev in events_res.data or []:
            payload = ev.get("payload") or {}
            cid = payload.get("contact_id")
            if cid and cid in c_ids:
                meta_by_id[cid] = payload

        for c in need_hydration:
            cid = str(c.get("id"))
            meta = meta_by_id.get(cid)
            if meta:
                if c.get("location") is None:
                    c["location"] = meta.get("location")
                if c.get("source_url") is None:
                    c["source_url"] = meta.get("source_url")
                if c.get("source_published_date") is None:
                    c["source_published_date"] = meta.get("source_published_date")
                if c.get("stale") is None:
                    c["stale"] = meta.get("stale")
                if c.get("confidence") is None:
                    c["confidence"] = meta.get("confidence")
                if "unverified" not in c or c.get("unverified") is None:
                    c["unverified"] = meta.get("unverified", False)
                if c.get("source") is None or c.get("source") == "seed":
                    if meta.get("source"):
                        c["source"] = meta.get("source")
    except Exception as e:
        logger.debug(f"Hydration from raw_events skipped: {e}")


def _get_suppressed_contact_ids(client: Client) -> set[str]:
    """Fetches suppressed contact IDs from raw_events (if table lacks suppressed_at column)."""
    suppressed = set()
    try:
        res = client.table("raw_events").select("payload").eq("source", "contact_suppression").execute()
        for ev in res.data or []:
            cid = (ev.get("payload") or {}).get("contact_id")
            if cid:
                suppressed.add(str(cid))
    except Exception:
        pass
    return suppressed


def search_data_lake(
    client: Client,
    query: str = "",
    filters: Optional[Dict[str, Any]] = None,
    actor_id: Optional[str] = None,
    include_sample: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Searches the shared contacts lake + companies/colleges.
    Always tried first. Excludes contacts where suppressed_at is not null.
    Sample (seed) contacts rank below real ones, and are excluded unless
    include_sample=True or DEMO_SHOW_SAMPLE=true in environment.
    Writes a raw_events audit row: source='search', payload={kind: 'data_lake', query, found: N}.
    """
    filters = filters or {}
    clean_query = query.strip() if query else ""
    tokens = [t.lower() for t in clean_query.split() if t]

    if include_sample is not None:
        show_sample = include_sample
    elif "include_sample" in filters:
        show_sample = bool(filters["include_sample"])
    else:
        show_sample = settings.DEMO_SHOW_SAMPLE or (
            os.environ.get("DEMO_SHOW_SAMPLE", "").lower() in ("true", "1", "yes")
        )

    # 1. Fetch reference lookup maps for companies and colleges
    try:
        companies_res = client.table("companies").select("id, name, category, industry").execute()
    except Exception:
        companies_res = client.table("companies").select("id, name, industry").execute()
    companies_data = companies_res.data or []
    company_name_map = {str(c["id"]): c.get("name") for c in companies_data}

    colleges_res = client.table("colleges").select("id, name, city").execute()
    colleges_data = colleges_res.data or []
    college_name_map = {str(c["id"]): c.get("name") for c in colleges_data}

    # Find company IDs or college IDs that match the query tokens
    from app.db.seed import MUMBAI_COMPANIES

    ref_map = {c["name"].lower(): c for c in MUMBAI_COMPANIES}

    matching_comp_ids = set()
    for c in companies_data:
        c_name = str(c.get("name", "")).lower()
        ref_cat = (ref_map.get(c_name) or {}).get("category", "")
        ref_ind = (ref_map.get(c_name) or {}).get("industry", "")
        db_cat = str(c.get("category", "")).lower()
        db_ind = str(c.get("industry", "")).lower()
        if any(
            t in c_name or t in ref_cat.lower() or t in ref_ind.lower() or t in db_cat or t in db_ind for t in tokens
        ):
            matching_comp_ids.add(str(c["id"]))

    matching_coll_ids = set()
    for col in colleges_data:
        col_name = str(col.get("name", "")).lower()
        if any(t in col_name for t in tokens):
            matching_coll_ids.add(str(col["id"]))

    # 2. Build contacts query
    try:
        db_query = client.table("contacts").select("*").is_("suppressed_at", "null")
        if filters.get("company_id"):
            db_query = db_query.eq("company_id", filters["company_id"])
        if filters.get("college_id"):
            db_query = db_query.eq("college_id", filters["college_id"])
        if filters.get("role_type"):
            db_query = db_query.eq("role_type", filters["role_type"])
        res = db_query.execute()
    except Exception:
        db_query = client.table("contacts").select("*")
        if filters.get("company_id"):
            db_query = db_query.eq("company_id", filters["company_id"])
        res = db_query.execute()

    contacts_pool = res.data or []
    _hydrate_contacts_metadata(client, contacts_pool)
    suppressed_ids = _get_suppressed_contact_ids(client)

    # 3. Filter contacts in Python for multi-field search (name, title, company_name, college_name)
    matched_contacts: List[Dict[str, Any]] = []
    for contact in contacts_pool:
        cid = str(contact.get("id"))
        # Extra safety check for suppression
        if contact.get("suppressed_at") is not None or cid in suppressed_ids:
            continue

        c_name = str(contact.get("name") or contact.get("full_name") or "").lower()
        c_title = str(contact.get("title", "")).lower()
        comp_id = str(contact.get("company_id")) if contact.get("company_id") else None
        coll_id = str(contact.get("college_id")) if contact.get("college_id") else None

        comp_name = company_name_map.get(comp_id, "") if comp_id else ""
        coll_name = college_name_map.get(coll_id, "") if coll_id else ""

        # Check match
        if not clean_query:
            is_match = True
        else:
            is_match = False
            # Check if any token matches contact name, title, company, or college
            for token in tokens:
                t_stem = (
                    token[:-2]
                    if token.endswith(("er", "or", "ed"))
                    else (token[:-3] if token.endswith("ing") else token)
                )
                if (
                    token in c_name
                    or token in c_title
                    or (t_stem and len(t_stem) >= 4 and t_stem in c_title)
                    or token in comp_name.lower()
                    or token in coll_name.lower()
                    or comp_id in matching_comp_ids
                    or coll_id in matching_coll_ids
                ):
                    is_match = True
                    break

        if is_match:
            is_sample = contact.get("source") == "seed" or (
                contact.get("note") == "synthetic" and contact.get("source") != "web"
            )
            if not show_sample and is_sample:
                continue

            enriched = dict(contact)
            if enriched.get("email") and str(enriched["email"]).endswith("@unverified.placeholder"):
                enriched["email"] = None
            enriched["name"] = contact.get("name") or contact.get("full_name") or ""
            enriched["company_name"] = comp_name
            enriched["college_name"] = coll_name
            enriched["is_sample"] = is_sample
            enriched["location"] = contact.get("location")
            enriched["source"] = contact.get("source") or "web"
            enriched["source_url"] = contact.get("source_url")
            enriched["source_published_date"] = contact.get("source_published_date")
            enriched["stale"] = contact.get("stale")
            enriched["confidence"] = (
                float(contact.get("confidence", 0.6)) if contact.get("confidence") is not None else 0.6
            )
            enriched["unverified"] = (
                bool(contact.get("unverified"))
                or (contact.get("source") == "web" and float(enriched["confidence"]) <= 0.6)
                or (contact.get("source") == "user_said")
                or False
            )
            matched_contacts.append(enriched)

    # Order: real contacts rank above sample ones; within real, Mumbai-stated and fresh contacts rank highest
    def _rank_contact(c: Dict[str, Any]):
        sample_key = 1 if c.get("is_sample") else 0
        loc = (c.get("location") or "").lower()
        mumbai_key = 0 if "mumbai" in loc else 1
        stale_val = c.get("stale")
        if stale_val is False:
            stale_key = 0
        elif stale_val is None:
            stale_key = 1
        else:
            stale_key = 2
        conf_key = -float(c.get("confidence") or 0.0)
        return (sample_key, mumbai_key, stale_key, conf_key)

    matched_contacts.sort(key=_rank_contact)
    found_count = len(matched_contacts)

    # 4. Write audit raw_events row (source='search')
    if actor_id:
        try:
            write_raw_event(
                actor_id,
                source="search",
                payload={
                    "kind": "data_lake",
                    "query": clean_query,
                    "found": found_count,
                    "filters": filters,
                },
                client=client,
            )
        except Exception as e:
            logger.warning(f"Could not record search raw_event: {e}")

    logger.info(f"search_data_lake: query='{clean_query}', filters={filters}, found={found_count}")

    return {
        "contacts": matched_contacts,
        "found": found_count,
        "query": clean_query,
    }
