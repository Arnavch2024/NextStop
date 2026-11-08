import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from supabase import Client

from app.logger import logger
from app.models.db import UserProfile


def normalize_name(name: str) -> str:
    """Normalizes contact name for deduplication comparison."""
    if not name:
        return ""
    n = name.strip().lower()
    # Remove titles/prefixes like Dr., Prof., Mr., Ms.
    n = re.sub(r"^(dr\.|prof\.|mr\.|ms\.|mrs\.)\s+", "", n)
    # Collapse spaces
    return re.sub(r"\s+", " ", n)


def get_or_create_company(client: Client, company_name: str, user_id: str) -> Optional[str]:
    """Finds or creates a company by lower(name). Returns company_id."""
    clean = company_name.strip()
    if not clean:
        return None
    res = client.table("companies").select("id, name").ilike("name", clean).execute()
    if res.data and len(res.data) > 0:
        return str(res.data[0]["id"])

    cid = str(uuid.uuid4())
    ins = (
        client.table("companies")
        .insert(
            {
                "id": cid,
                "name": clean,
                "owner_id": user_id,
            }
        )
        .execute()
    )
    if ins.data and len(ins.data) > 0:
        return str(ins.data[0].get("id", cid))
    return cid


def get_or_create_college(client: Client, college_name: str, user_id: str) -> Optional[str]:
    """Finds or creates a college by lower(name) in Mumbai. Returns college_id."""
    clean = college_name.strip()
    if not clean:
        return None
    res = client.table("colleges").select("id, name").ilike("name", clean).execute()
    if res.data and len(res.data) > 0:
        return str(res.data[0]["id"])

    cid = str(uuid.uuid4())
    ins = (
        client.table("colleges")
        .insert(
            {
                "id": cid,
                "name": clean,
                "city": "Mumbai",
                "owner_id": user_id,
            }
        )
        .execute()
    )
    if ins.data and len(ins.data) > 0:
        return str(ins.data[0].get("id", cid))
    return cid


def upsert_contact(
    client: Client,
    candidate: Dict[str, Any],
    user: UserProfile,
    source: str = "web",
    source_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Multi-key dedupe and prioritized merge for shared contacts lake.
    Match order:
      1. linkedin_url (case-insensitive) if present
      2. email (case-insensitive) if present
      3. normalized name + company_id

    Priority:
      web (with source_url) > user_said > seed.

    Rules:
      - Lake NEVER stores a phone number.
      - user_said fills empty fields only (never overwrites); conflicts go to user_saved_contacts.
      - Provenance appended to contact_sources.
      - Always returns {"contact_id": id, "op": "created" | "merged"}.
    """
    data = dict(candidate)

    # Hard rule: drop phone from lake data
    phone_override = data.pop("phone", None)
    data.pop("owner_id", None)

    name = data.get("name") or data.get("full_name") or ""
    name = name.strip()
    if not name:
        # Drop nameless candidate
        logger.info("Dropping nameless contact candidate.")
        return {"error": "nameless_candidate"}

    user_id = str(user.id)
    now_iso = datetime.now(timezone.utc).isoformat()

    # Resolve company_id if company name given as string
    company_id = data.get("company_id")
    if not company_id and data.get("company"):
        company_id = get_or_create_company(client, data["company"], user_id)
    if not company_id and data.get("company_name"):
        company_id = get_or_create_company(client, data["company_name"], user_id)

    # Resolve college_id if college name given as string
    college_id = data.get("college_id")
    if not college_id and data.get("college"):
        college_id = get_or_create_college(client, data["college"], user_id)
    if not college_id and data.get("college_name"):
        college_id = get_or_create_college(client, data["college_name"], user_id)

    email = data.get("email", "").strip().lower() if data.get("email") else None
    linkedin = data.get("linkedin_url", "").strip().lower() if data.get("linkedin_url") else None
    role_type = data.get("role_type") or "other"
    title = data.get("title")

    # 1. Match against existing (non-suppressed) contacts
    existing = None

    # Step 1: linkedin_url
    if linkedin:
        q = client.table("contacts").select("*").ilike("linkedin_url", linkedin).is_("suppressed_at", "null").execute()
        if q.data and len(q.data) > 0:
            existing = q.data[0]

    # Step 2: email
    if not existing and email:
        q = client.table("contacts").select("*").ilike("email", email).is_("suppressed_at", "null").execute()
        if q.data and len(q.data) > 0:
            existing = q.data[0]

    # Step 3: normalized name + company_id
    if not existing and name and company_id:
        q = client.table("contacts").select("*").eq("company_id", company_id).is_("suppressed_at", "null").execute()
        candidates = q.data or []
        for cand in candidates:
            if normalize_name(cand.get("name", "")) == normalize_name(name):
                existing = cand
                break

    op = "created"

    if existing:
        op = "merged"
        contact_id = str(existing["id"])
        existing_source = existing.get("source", "seed")

        update_fields: Dict[str, Any] = {}
        conflicts: Dict[str, Any] = {}

        if source == "web":
            # web (with source_url) > user_said > seed
            # Web may overwrite empty or lower-priority fields
            if title and (not existing.get("title") or existing_source in ("seed", "user_said")):
                update_fields["title"] = title
            if email and (not existing.get("email") or existing_source in ("seed", "user_said")):
                update_fields["email"] = email
            if linkedin and (not existing.get("linkedin_url") or existing_source in ("seed", "user_said")):
                update_fields["linkedin_url"] = linkedin
            if company_id and not existing.get("company_id"):
                update_fields["company_id"] = company_id
            if college_id and not existing.get("college_id"):
                update_fields["college_id"] = college_id
            if role_type and role_type != "other" and existing.get("role_type") in ("other", None):
                update_fields["role_type"] = role_type

            update_fields["source"] = "web"
            update_fields["source_url"] = source_url or data.get("source_url")
            update_fields["last_verified_at"] = now_iso
            update_fields["confidence"] = data.get("confidence", 1.0)

        elif source == "user_said":
            # user_said fills empty fields only, never overwrites
            candidate_fields = {
                "title": title,
                "email": email,
                "linkedin_url": linkedin,
                "role_type": role_type if role_type != "other" else None,
                "company_id": company_id,
                "college_id": college_id,
            }

            for field, val in candidate_fields.items():
                if val:
                    curr_val = existing.get(field)
                    if not curr_val:
                        update_fields[field] = val
                    elif str(curr_val).strip().lower() != str(val).strip().lower():
                        # Conflict! Lake stays unchanged, conflict goes to user_saved_contacts
                        conflicts[field] = val

            # If phone was provided by user, record as conflict/override for user's private list
            if phone_override:
                conflicts["phone"] = phone_override

        if update_fields:
            client.table("contacts").update(update_fields).eq("id", contact_id).execute()

        # Handle user_said conflicts: store in user's private user_saved_contacts
        if (conflicts or phone_override) and source == "user_said":
            save_q = (
                client.table("user_saved_contacts")
                .select("id, user_overrides")
                .eq("profile_id", user_id)
                .eq("contact_id", contact_id)
                .execute()
            )
            if save_q.data and len(save_q.data) > 0:
                row_id = save_q.data[0]["id"]
                existing_overrides = save_q.data[0].get("user_overrides") or {}
                existing_overrides.update(conflicts)
                client.table("user_saved_contacts").update(
                    {
                        "user_overrides": existing_overrides,
                        "phone": phone_override or save_q.data[0].get("phone"),
                        "unverified": True,
                    }
                ).eq("id", row_id).execute()
            else:
                client.table("user_saved_contacts").insert(
                    {
                        "id": str(uuid.uuid4()),
                        "profile_id": user_id,
                        "contact_id": contact_id,
                        "user_overrides": conflicts,
                        "phone": phone_override,
                        "unverified": True,
                    }
                ).execute()

    else:
        # Create new contact
        contact_id = str(uuid.uuid4())
        new_row = {
            "id": contact_id,
            "name": name,
            "title": title,
            "company_id": company_id,
            "college_id": college_id,
            "role_type": role_type,
            "email": email,
            "linkedin_url": linkedin,
            "source": source,
            "source_url": source_url or data.get("source_url"),
            "confidence": data.get("confidence", 1.0),
            "created_by_profile_id": user_id,
            "first_seen_at": now_iso,
            "last_verified_at": now_iso if source == "web" else None,
        }
        ins = client.table("contacts").insert(new_row).execute()
        if ins.data and len(ins.data) > 0:
            contact_id = str(ins.data[0].get("id", contact_id))

        if phone_override and source == "user_said":
            # Save user phone in private user_saved_contacts
            client.table("user_saved_contacts").insert(
                {
                    "id": str(uuid.uuid4()),
                    "profile_id": user_id,
                    "contact_id": contact_id,
                    "phone": phone_override,
                    "unverified": True,
                }
            ).execute()

    # Append provenance in contact_sources
    source_row = {
        "id": str(uuid.uuid4()),
        "contact_id": contact_id,
        "source": source,
        "source_url": source_url or data.get("source_url"),
        "fetched_at": now_iso if source == "web" else None,
        "confidence": data.get("confidence", 1.0),
        "unverified": (source == "user_said"),
        "note": data.get("note"),
    }
    try:
        client.table("contact_sources").insert(source_row).execute()
    except Exception as e:
        logger.warning(f"Could not record contact_sources row: {e}")

    logger.info(f"upsert_contact {op}: id={contact_id}, source={source}")
    return {"contact_id": contact_id, "op": op}
