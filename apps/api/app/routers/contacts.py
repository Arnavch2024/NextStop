import os
import uuid
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.config import settings
from app.db.supabase import get_supabase_client
from app.dependencies import get_current_user
from app.logger import logger
from app.models.api import (
    ContactCard,
    ContactListResponse,
    ContactSourceModel,
    SaveContactRequest,
    SaveResponse,
)
from app.models.db import UserProfile
from app.search.data_lake import _get_suppressed_contact_ids, _hydrate_contacts_metadata

router = APIRouter(prefix="/v1/contacts", tags=["Contacts"])


@router.get(
    "",
    response_model=ContactListResponse,
    summary="Search the shared contact lake + own saved list",
    description="Lists contacts from the shared lake and/or private saved list. Excludes suppressed contacts.",
)
def list_contacts(
    q: Optional[str] = Query(None, description="Free text search query"),
    company_id: Optional[str] = Query(None, description="Filter by company UUID"),
    college_id: Optional[str] = Query(None, description="Filter by college UUID"),
    role_type: Optional[str] = Query(None, description="Filter by role type"),
    saved_only: bool = Query(False, description="Filter to only contacts saved by caller"),
    include_sample: Optional[bool] = Query(None, description="Include sample/seed data in results"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    current_user: UserProfile = Depends(get_current_user),
    client: Client = Depends(get_supabase_client),
) -> ContactListResponse:
    if not current_user.role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not assigned. Please complete onboarding at /onboarding.",
        )
    # 1. Fetch caller's saved contacts
    try:
        saved_res = client.table("user_saved_contacts").select("contact_id").eq("profile_id", current_user.id).execute()
        saved_contact_ids = {str(r["contact_id"]) for r in (saved_res.data or []) if r.get("contact_id")}
    except Exception:
        saved_contact_ids = set()

    if saved_only and not saved_contact_ids:
        return ContactListResponse(items=[], page=page, page_size=page_size, total=0)

    # 2. Reference lookups for company and college names
    comp_res = client.table("companies").select("id, name").execute()
    comp_map = {str(c["id"]): c.get("name") for c in (comp_res.data or []) if c.get("id")}

    coll_res = client.table("colleges").select("id, name").execute()
    coll_map = {str(c["id"]): c.get("name") for c in (coll_res.data or []) if c.get("id")}

    # 3. Base contacts query (exclude suppressed_at is not null)
    try:
        query_builder = client.table("contacts").select("*").is_("suppressed_at", "null")
        if company_id:
            query_builder = query_builder.eq("company_id", company_id)
        if college_id:
            query_builder = query_builder.eq("college_id", college_id)
        if role_type:
            query_builder = query_builder.eq("role_type", role_type)
        contacts_res = query_builder.execute()
    except Exception:
        query_builder = client.table("contacts").select("*")
        if company_id:
            query_builder = query_builder.eq("company_id", company_id)
        contacts_res = query_builder.execute()

    raw_contacts = contacts_res.data or []
    _hydrate_contacts_metadata(client, raw_contacts)
    suppressed_ids = _get_suppressed_contact_ids(client)

    # 4. Filter in memory for saved_only, q text search, suppression, and sample data controls
    clean_q = q.strip().lower() if q else ""
    tokens = [t for t in clean_q.split() if t]

    show_sample = (
        include_sample
        if include_sample is not None
        else (settings.DEMO_SHOW_SAMPLE or (os.environ.get("DEMO_SHOW_SAMPLE", "").lower() in ("true", "1", "yes")))
    )

    matched: list[dict] = []
    for c in raw_contacts:
        cid = str(c["id"])
        if c.get("suppressed_at") is not None or cid in suppressed_ids:
            continue
        if saved_only and cid not in saved_contact_ids:
            continue

        is_sample_val = c.get("source") == "seed" or (c.get("note") == "synthetic" and c.get("source") != "web")
        if not show_sample and is_sample_val:
            continue

        c_name = str(c.get("name") or c.get("full_name") or "").lower()
        c_title = str(c.get("title", "")).lower()
        c_email = str(c.get("email", "")).lower()
        comp_name = comp_map.get(str(c.get("company_id", "")), "")
        coll_name = coll_map.get(str(c.get("college_id", "")), "")

        if tokens:
            matches_token = False
            for t in tokens:
                if t in c_name or t in c_title or t in c_email or t in comp_name.lower() or t in coll_name.lower():
                    matches_token = True
                    break
            if not matches_token:
                continue

        item = dict(c)
        item["company_name"] = comp_name or None
        item["college_name"] = coll_name or None
        item["saved"] = cid in saved_contact_ids
        item["is_sample"] = is_sample_val
        matched.append(item)

    # Order: real contacts rank above sample ones; within real, Mumbai-stated and fresh contacts rank highest
    def _rank_contact(c: dict):
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

    matched.sort(key=_rank_contact)

    total = len(matched)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paged = matched[start_idx:end_idx]

    # 5. Fetch contact_sources for paged contacts
    paged_ids = [str(c["id"]) for c in paged]
    sources_by_contact: dict[str, list[ContactSourceModel]] = {cid: [] for cid in paged_ids}
    if paged_ids:
        try:
            sources_res = client.table("contact_sources").select("*").in_("contact_id", paged_ids).execute()
            for s in sources_res.data or []:
                s_cid = str(s.get("contact_id"))
                if s_cid in sources_by_contact:
                    s_url = s.get("source_url")
                    domain = urlparse(s_url).netloc if s_url else None
                    sources_by_contact[s_cid].append(
                        ContactSourceModel(
                            source=s.get("source", "seed"),
                            source_url=s_url,
                            domain=domain,
                            fetched_at=s.get("fetched_at"),
                            confidence=float(s.get("confidence", 1.0) or 1.0),
                        )
                    )
        except Exception as e:
            logger.warning(f"Failed to fetch contact_sources: {e}")

    # Build response cards
    cards: list[ContactCard] = []
    for c in paged:
        cid = str(c["id"])
        c_sources = sources_by_contact.get(cid, [])
        if not c_sources and c.get("source"):
            s_url = c.get("source_url")
            domain = urlparse(s_url).netloc if s_url else None
            c_sources = [
                ContactSourceModel(
                    source=c.get("source", "seed"),
                    source_url=s_url,
                    domain=domain,
                    fetched_at=c.get("created_at"),
                    confidence=1.0,
                )
            ]

        is_sample_val = (
            c.get("is_sample")
            if "is_sample" in c
            else (c.get("source") == "seed" or (c.get("note") == "synthetic" and c.get("source") != "web"))
        )

        email_val = c.get("email")
        if email_val and str(email_val).endswith("@unverified.placeholder"):
            email_val = None

        cards.append(
            ContactCard(
                id=cid,
                name=c.get("name") or c.get("full_name") or "",
                title=c.get("title"),
                company_id=str(c.get("company_id")) if c.get("company_id") else None,
                company_name=c.get("company_name"),
                college_id=str(c.get("college_id")) if c.get("college_id") else None,
                college_name=c.get("college_name"),
                role_type=c.get("role_type", "other"),
                email=email_val,
                linkedin_url=c.get("linkedin_url"),
                location=c.get("location"),
                source=c.get("source") or (c_sources[0].source if c_sources else "web"),
                source_url=c.get("source_url") or (c_sources[0].source_url if c_sources else None),
                source_published_date=c.get("source_published_date"),
                stale=c.get("stale"),
                confidence=(
                    float(c.get("confidence"))
                    if c.get("confidence") is not None
                    else (c_sources[0].confidence if c_sources else 0.6)
                ),
                unverified=(
                    bool(c.get("unverified"))
                    or (c.get("source") == "web" and float(c.get("confidence", 1.0) or 1.0) <= 0.6)
                    or (c.get("source") == "user_said")
                    or False
                ),
                saved=c.get("saved", False),
                is_sample=is_sample_val,
                sources=c_sources,
                first_seen_at=c.get("first_seen_at") or c.get("created_at"),
                last_verified_at=c.get("last_verified_at"),
            )
        )

    return ContactListResponse(
        items=cards,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "/{id}/save",
    response_model=SaveResponse,
    summary="Save a contact to my list",
    description="Saves a shared-lake contact to the user's private list. Optional phone stored privately only.",
)
def save_contact(
    id: str,
    body: Optional[SaveContactRequest] = None,
    current_user: UserProfile = Depends(get_current_user),
    client: Client = Depends(get_supabase_client),
) -> SaveResponse:
    # Check if contact exists
    contact_res = client.table("contacts").select("id").eq("id", id).execute()
    if not contact_res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

    # Check if already saved
    existing_res = (
        client.table("user_saved_contacts")
        .select("id, phone")
        .eq("profile_id", current_user.id)
        .eq("contact_id", id)
        .execute()
    )

    phone_val = body.phone if body and body.phone else None

    if existing_res.data:
        # Update phone if provided
        saved_id = existing_res.data[0]["id"]
        update_payload: dict = {}
        if phone_val:
            update_payload["phone"] = phone_val
        if update_payload:
            client.table("user_saved_contacts").update(update_payload).eq("id", saved_id).execute()
    else:
        new_row = {
            "id": str(uuid.uuid4()),
            "profile_id": current_user.id,
            "contact_id": id,
            "phone": phone_val,
        }
        client.table("user_saved_contacts").insert(new_row).execute()

    return SaveResponse(contact_id=id, saved=True)


@router.delete(
    "/{id}/save",
    response_model=SaveResponse,
    summary="Remove a saved contact (delete-my-saved-contact)",
    description="Removes a contact from the user's private list. Lake contact remains untouched.",
)
def remove_saved_contact(
    id: str,
    current_user: UserProfile = Depends(get_current_user),
    client: Client = Depends(get_supabase_client),
) -> SaveResponse:
    client.table("user_saved_contacts").delete().eq("profile_id", current_user.id).eq("contact_id", id).execute()
    return SaveResponse(contact_id=id, saved=False)
