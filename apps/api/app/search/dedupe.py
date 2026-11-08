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
    owner = user_id if user_id and user_id != "00000000-0000-0000-0000-000000000000" else None
    ins = (
        client.table("companies")
        .insert(
            {
                "id": cid,
                "name": clean,
                "owner_id": owner,
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
    owner = user_id if user_id and user_id != "00000000-0000-0000-0000-000000000000" else None
    ins = (
        client.table("colleges")
        .insert(
            {
                "id": cid,
                "name": clean,
                "city": "Mumbai",
                "owner_id": owner,
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

    # Resolve company_id if company name given as string or if company_id is not a valid UUID
    company_id = data.get("company_id")
    if company_id:
        try:
            uuid.UUID(str(company_id))
        except (ValueError, AttributeError):
            company_id = None

    if not company_id and data.get("company"):
        company_id = get_or_create_company(client, data["company"], user_id)
    if not company_id and data.get("company_name"):
        company_id = get_or_create_company(client, data["company_name"], user_id)

    # Resolve college_id if college name given as string or if college_id is not a valid UUID
    college_id = data.get("college_id")
    if college_id:
        try:
            uuid.UUID(str(college_id))
        except (ValueError, AttributeError):
            college_id = None

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
        try:
            q = (
                client.table("contacts")
                .select("*")
                .ilike("linkedin_url", linkedin)
                .is_("suppressed_at", "null")
                .execute()
            )
            if q.data and len(q.data) > 0:
                existing = q.data[0]
        except Exception:
            try:
                q = client.table("contacts").select("*").ilike("linkedin_url", linkedin).execute()
                if q.data and len(q.data) > 0:
                    existing = q.data[0]
            except Exception:
                pass

    # Step 2: email
    if not existing and email:
        try:
            q = client.table("contacts").select("*").ilike("email", email).is_("suppressed_at", "null").execute()
            if q.data and len(q.data) > 0:
                existing = q.data[0]
        except Exception:
            try:
                q = client.table("contacts").select("*").ilike("email", email).execute()
                if q.data and len(q.data) > 0:
                    existing = q.data[0]
            except Exception:
                pass

    # Step 3: normalized name + company_id
    if not existing and name and company_id:
        try:
            q = client.table("contacts").select("*").eq("company_id", company_id).is_("suppressed_at", "null").execute()
            candidates = q.data or []
        except Exception:
            try:
                q = client.table("contacts").select("*").eq("company_id", company_id).execute()
                candidates = q.data or []
            except Exception:
                candidates = []
        for cand in candidates:
            cand_name = cand.get("name") or cand.get("full_name") or ""
            if normalize_name(cand_name) == normalize_name(name):
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

            if data.get("location"):
                update_fields["location"] = data["location"]
            if data.get("published_date") or data.get("source_published_date"):
                update_fields["source_published_date"] = data.get("published_date") or data.get("source_published_date")
            if "stale" in data:
                update_fields["stale"] = data["stale"]

            update_fields["source"] = "web"
            update_fields["source_url"] = source_url or data.get("source_url")
            update_fields["last_verified_at"] = now_iso
            # Confidence capping: 0.4 if stale, 0.6 if not stale for single unfetched source
            fetch_status = data.get("fetch_status")
            is_unverified = (fetch_status != "ok") or (not data.get("verified", False))
            conf = float(data.get("confidence", 1.0))
            if is_unverified:
                if data.get("stale") is True:
                    conf = min(conf, 0.4)
                else:
                    conf = min(conf, 0.6)
            update_fields["confidence"] = conf

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
            try:
                client.table("contacts").update(update_fields).eq("id", contact_id).execute()
            except Exception:
                compat_updates = {}
                for k, v in update_fields.items():
                    if k == "name":
                        compat_updates["full_name"] = v
                    elif k in ("title", "email", "company_id"):
                        compat_updates[k] = v
                if compat_updates:
                    try:
                        client.table("contacts").update(compat_updates).eq("id", contact_id).execute()
                    except Exception as e_up:
                        logger.warning(f"Could not update contact compatibly: {e_up}")

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
        fetch_status = data.get("fetch_status")
        is_single_unverified = (
            (source == "user_said")
            or data.get("unverified", False)
            or (fetch_status != "ok")
            or (not data.get("verified", False))
        )
        conf = float(data.get("confidence", 1.0))
        if is_single_unverified and source == "web":
            if data.get("stale") is True:
                conf = min(conf, 0.4)
            else:
                conf = min(conf, 0.6)

        new_row = {
            "id": contact_id,
            "name": name,
            "title": title,
            "company_id": company_id,
            "college_id": college_id,
            "role_type": role_type,
            "email": email,
            "linkedin_url": linkedin,
            "location": data.get("location"),
            "source_published_date": data.get("published_date") or data.get("source_published_date"),
            "stale": data.get("stale"),
            "source": source,
            "source_url": source_url or data.get("source_url"),
            "confidence": conf,
            "created_by_profile_id": user_id if user_id and user_id != "00000000-0000-0000-0000-000000000000" else None,
            "first_seen_at": now_iso,
            "last_verified_at": now_iso if source == "web" else None,
        }
        try:
            ins = client.table("contacts").insert(new_row).execute()
            if ins.data and len(ins.data) > 0:
                contact_id = str(ins.data[0].get("id", contact_id))
        except Exception:
            # If the database has the legacy unique index (company_id, lower(coalesce(email,''))),
            # contacts without emails would collide on (company_id, ''). Use a unique placeholder.
            compat_email = email or f"{contact_id}@unverified.placeholder"
            compat_row = {
                "id": contact_id,
                "full_name": name,
                "title": title,
                "company_id": company_id,
                "email": compat_email,
                "owner_id": None,
            }
            ins = client.table("contacts").insert(compat_row).execute()
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
    fetch_status = data.get("fetch_status")
    is_source_unverified = (
        (source == "user_said")
        or data.get("unverified", False)
        or (fetch_status != "ok")
        or (not data.get("verified", False))
    )
    conf = float(data.get("confidence", 1.0))
    if is_source_unverified and source == "web":
        conf = min(conf, 0.6)

    source_row = {
        "id": str(uuid.uuid4()),
        "contact_id": contact_id,
        "source": source,
        "source_url": source_url or data.get("source_url"),
        "fetched_at": now_iso if source == "web" else None,
        "confidence": conf,
        "unverified": is_source_unverified,
        "fetch_status": fetch_status or ("ok" if source == "seed" else "not_fetched"),
        "published_date": data.get("published_date"),
        "note": "synthetic"
        if data.get("note") == "synthetic"
        else f"fetch_status={fetch_status};published_date={data.get('published_date')}",
    }
    try:
        client.table("contact_sources").insert(source_row).execute()
    except Exception:
        clean_row = {k: v for k, v in source_row.items() if k not in ("fetch_status", "published_date")}
        try:
            client.table("contact_sources").insert(clean_row).execute()
        except Exception as e2:
            logger.warning(f"Could not record contact_sources row: {e2}")

    logger.info(f"upsert_contact {op}: id={contact_id}, source={source}")
    return {"contact_id": contact_id, "op": op}
