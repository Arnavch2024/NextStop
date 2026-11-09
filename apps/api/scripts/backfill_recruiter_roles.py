#!/usr/bin/env python3
"""
One-off backfill script:
Updates role_type to 'campus_recruiter' for non-suppressed web contacts
whose title matches campus/university/early-careers.
Prints the count and names changed.
No migrations required.
"""

import sys
from pathlib import Path

# Add project root to sys.path
api_root = Path(__file__).resolve().parent.parent
if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))

from app.db.supabase import get_supabase_client  # noqa: E402
from app.search.dedupe import classify_recruiter_role  # noqa: E402


def main() -> int:
    client = get_supabase_client()
    if not client:
        print("ERROR: Supabase client not initialized. Check your credentials.")
        return 1

    # Query non-suppressed web contacts
    res = (
        client.table("contacts")
        .select("id, name, title, role_type, suppressed_at, source")
        .eq("source", "web")
        .is_("suppressed_at", "null")
        .execute()
    )

    rows = res.data or []
    changed_names = []

    print(f"Scanned {len(rows)} non-suppressed web contacts.")

    for row in rows:
        cid = row["id"]
        name = row.get("name") or "Unknown"
        title = row.get("title") or ""
        curr_role = row.get("role_type")

        # Classify role based on title
        new_role = classify_recruiter_role(title, default_role=curr_role or "other")
        if new_role == "campus_recruiter" and curr_role != "campus_recruiter":
            # Update role_type in contacts
            client.table("contacts").update({"role_type": "campus_recruiter"}).eq("id", cid).execute()
            changed_names.append(f"{name} (title: '{title}', previous: '{curr_role}')")

    print("\nBackfill Summary:")
    print(f"Total contacts updated: {len(changed_names)}")
    for item in changed_names:
        print(f"  - {item}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
