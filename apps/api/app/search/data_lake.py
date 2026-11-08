import os
from typing import Any, Dict, List, Optional

from supabase import Client

from app.config import settings
from app.db.supabase import write_raw_event
from app.logger import logger


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
    companies_res = client.table("companies").select("id, name, category, industry").execute()
    companies_data = companies_res.data or []
    company_name_map = {str(c["id"]): c.get("name") for c in companies_data}

    colleges_res = client.table("colleges").select("id, name, city").execute()
    colleges_data = colleges_res.data or []
    college_name_map = {str(c["id"]): c.get("name") for c in colleges_data}

    # Find company IDs or college IDs that match the query tokens
    matching_comp_ids = set()
    for c in companies_data:
        c_name = str(c.get("name", "")).lower()
        if any(t in c_name for t in tokens):
            matching_comp_ids.add(str(c["id"]))

    matching_coll_ids = set()
    for col in colleges_data:
        col_name = str(col.get("name", "")).lower()
        if any(t in col_name for t in tokens):
            matching_coll_ids.add(str(col["id"]))

    # 2. Build contacts query
    db_query = client.table("contacts").select("*").is_("suppressed_at", "null")

    if filters.get("company_id"):
        db_query = db_query.eq("company_id", filters["company_id"])
    if filters.get("college_id"):
        db_query = db_query.eq("college_id", filters["college_id"])
    if filters.get("role_type"):
        db_query = db_query.eq("role_type", filters["role_type"])

    res = db_query.execute()
    contacts_pool = res.data or []

    # 3. Filter contacts in Python for multi-field search (name, title, company_name, college_name)
    matched_contacts: List[Dict[str, Any]] = []
    for contact in contacts_pool:
        # Extra safety check for suppression
        if contact.get("suppressed_at") is not None:
            continue

        c_name = str(contact.get("name", "")).lower()
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
                if (
                    token in c_name
                    or token in c_title
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
            enriched["company_name"] = comp_name
            enriched["college_name"] = coll_name
            enriched["is_sample"] = is_sample
            matched_contacts.append(enriched)

    # Order: real (non-seed) contacts rank above sample ones
    matched_contacts.sort(key=lambda c: 1 if c.get("is_sample") else 0)
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
