import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from supabase import Client

from app.logger import logger
from app.models.db import UserProfile


def generate_outreach_text(
    contact: Dict[str, Any],
    channel: str,
    sender_context: Optional[str] = None,
    user: Optional[UserProfile] = None,
) -> Dict[str, Optional[str]]:
    """
    Generates tailored subject and body for outreach.
    Never sends anything.
    """
    c_name = contact.get("name") or "Hiring Team"
    c_title = contact.get("title") or "Recruiter"
    c_company = contact.get("company_name") or "your team"
    c_role_type = contact.get("role_type", "other")

    sender_name = user.display_name if user and user.display_name else "NextStop Representative"
    sender_role = user.role.value if user and user.role else "recruiting partner"
    ctx = f" Note: {sender_context.strip()}" if sender_context and sender_context.strip() else ""

    if channel == "linkedin":
        subject = None
        body = (
            f"Hi {c_name}, I noticed your work as {c_title} at {c_company}. "
            f"I am reaching out regarding campus recruiting partnerships for Mumbai's 2027/2028 batches.{ctx} "
            f"Would love to connect!"
        )
    else:
        # Default: email
        if c_role_type == "placement_officer":
            subject = "Campus Recruitment Partnership — Mumbai 2027/2028 Batches"
            body = (
                f"Dear {c_name},\n\n"
                f"Hope this email finds you well. I am reaching out regarding campus hiring opportunities for "
                f"Mumbai students graduating in 2027 and 2028.{ctx}\n\n"
                f"We would welcome the opportunity to connect with your placement department to discuss hiring timelines "
                f"and student engagement.\n\n"
                f"Best regards,\n"
                f"{sender_name}\n"
                f"{sender_role.replace('_', ' ').capitalize()}"
            )
        else:
            subject = f"Campus Talent Inquiry — {c_company} & Mumbai 2027/2028 Graduates"
            body = (
                f"Hi {c_name},\n\n"
                f"Hope you are having a productive week. I am reaching out to you as {c_title} at {c_company} "
                f"regarding our emerging talent pipeline across Mumbai colleges for 2027 and 2028 batches.{ctx}\n\n"
                f"We would love to share pre-assessed candidates and discuss how we can support your campus hiring goals.\n\n"
                f"Best regards,\n"
                f"{sender_name}\n"
                f"{sender_role.replace('_', ' ').capitalize()}"
            )

    return {"subject": subject, "body": body}


def create_outreach_draft(
    client: Client,
    user: UserProfile,
    contact_id: str,
    channel: str = "email",
    sender_context: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates and stores an outreach draft for the caller.
    Never sends; stores privately in outreach_drafts with profile_id = user.id.
    """
    # 1. Fetch contact details
    contact_res = client.table("contacts").select("*").eq("id", contact_id).execute()
    contact = contact_res.data[0] if (contact_res.data and len(contact_res.data) > 0) else {}

    # Resolve company name if present
    company_name = None
    if contact.get("company_id"):
        comp_res = client.table("companies").select("name").eq("id", contact["company_id"]).execute()
        if comp_res.data and len(comp_res.data) > 0:
            company_name = comp_res.data[0].get("name")
    contact["company_name"] = company_name

    # 2. Generate content
    draft_content = generate_outreach_text(contact, channel, sender_context, user)
    subject = draft_content["subject"]
    body = draft_content["body"] or ""

    # 3. Store private draft in outreach_drafts
    draft_id = str(uuid.uuid4())
    draft_row = {
        "id": draft_id,
        "profile_id": str(user.id),
        "contact_id": contact_id,
        "channel": channel,
        "subject": subject,
        "body": body,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    ins = client.table("outreach_drafts").insert(draft_row).execute()
    if ins.data and len(ins.data) > 0:
        draft_id = str(ins.data[0].get("id", draft_id))

    logger.info(f"Created outreach draft {draft_id} for user {user.id} (channel={channel})")

    return {
        "draft_id": draft_id,
        "subject": subject,
        "body": body,
        "channel": channel,
    }
