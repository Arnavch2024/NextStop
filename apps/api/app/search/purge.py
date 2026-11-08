from typing import Any, Dict

from supabase import Client

from app.logger import logger


def run_purge(client: Client, confirm: bool = False) -> Dict[str, Any]:
    """
    Finds and deletes source='seed' contacts and their contact_sources rows.
    Requires confirm=True to execute deletions.
    """
    # 1. Fetch seed contacts
    try:
        c_res = client.table("contacts").select("id").eq("source", "seed").execute()
        seed_contacts = c_res.data or []
        contact_count = len(seed_contacts)
    except Exception as exc:
        if "does not exist" in str(exc).lower():
            logger.warning(f"Contacts lake table or column not migrated: {exc}")
            return {
                "contacts_found": 0,
                "sources_found": 0,
                "contacts_deleted": 0,
                "sources_deleted": 0,
                "confirmed": confirm,
                "warning": "Migration 003_search_slice.sql has not been applied yet. Run 'supabase db push' first.",
            }
        raise exc

    # 2. Fetch seed contact sources
    try:
        s_res = client.table("contact_sources").select("id").eq("source", "seed").execute()
        seed_sources = s_res.data or []
        source_count = len(seed_sources)
    except Exception as exc:
        if "does not exist" in str(exc).lower():
            seed_sources = []
            source_count = 0
        else:
            raise exc

    logger.info(f"Purge seed scan found: {contact_count} contacts and {source_count} contact_sources")

    if not confirm:
        return {
            "contacts_found": contact_count,
            "sources_found": source_count,
            "contacts_deleted": 0,
            "sources_deleted": 0,
            "confirmed": False,
        }

    # Execute deletion
    sources_deleted = 0
    contacts_deleted = 0

    if source_count > 0:
        client.table("contact_sources").delete().eq("source", "seed").execute()
        sources_deleted = source_count

    if contact_count > 0:
        client.table("contacts").delete().eq("source", "seed").execute()
        contacts_deleted = contact_count

    logger.info(f"Purged {contacts_deleted} seed contacts and {sources_deleted} seed sources rows.")

    return {
        "contacts_found": contact_count,
        "sources_found": source_count,
        "contacts_deleted": contacts_deleted,
        "sources_deleted": sources_deleted,
        "confirmed": True,
    }
