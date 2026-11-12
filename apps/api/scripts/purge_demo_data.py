#!/usr/bin/env python3
"""
Stand-alone admin script to purge demo data.
Deletes ONLY rows flagged as demo data or tied to demo profiles:
- student_records where is_demo_data = true
- campus_hiring tied to demo profiles
- batch_sharing set by demo profiles
- synthetic internships & jobs (source='seed') tied to demo student profile
- sample placement officer contacts (source='seed') and their contact_sources

Requires explicit --yes flag to perform deletion.
"""

import argparse
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

# Add apps/api to path
api_root = Path(__file__).resolve().parent.parent
if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))

from supabase import Client  # noqa: E402

from app.db.supabase import get_supabase_client  # noqa: E402

DEMO_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "recruiting.demo.wildcatter")


def scan_demo_data(client: Client) -> Dict[str, Any]:
    """Scans for demo data rows across all relevant tables."""
    # 1. Fetch demo profiles
    demo_profs_res = client.table("profiles").select("id, role, is_demo").eq("is_demo", True).execute()
    demo_profile_ids = [str(p["id"]) for p in (demo_profs_res.data or [])]

    # 2. student_records (is_demo_data = true)
    stud_rec_res = client.table("student_records").select("id").eq("is_demo_data", True).execute()
    student_record_ids = [str(r["id"]) for r in (stud_rec_res.data or [])]

    # 3. campus_hiring (profile_id in demo_profile_ids)
    campus_hiring_ids = []
    if demo_profile_ids:
        ch_res = client.table("campus_hiring").select("id, profile_id").in_("profile_id", demo_profile_ids).execute()
        campus_hiring_ids = [str(r["id"]) for r in (ch_res.data or [])]

    # 4. batch_sharing (set_by_profile_id in demo_profile_ids)
    batch_sharing_ids = []
    if demo_profile_ids:
        bs_res = (
            client.table("batch_sharing")
            .select("id, set_by_profile_id")
            .in_("set_by_profile_id", demo_profile_ids)
            .execute()
        )
        batch_sharing_ids = [str(r["id"]) for r in (bs_res.data or [])]

    # 5. internships & jobs for demo profiles with source='seed'
    internship_ids = []
    job_ids = []
    if demo_profile_ids:
        int_res = (
            client.table("internships").select("id").in_("profile_id", demo_profile_ids).eq("source", "seed").execute()
        )
        internship_ids = [str(r["id"]) for r in (int_res.data or [])]

        job_res = client.table("jobs").select("id").in_("profile_id", demo_profile_ids).eq("source", "seed").execute()
        job_ids = [str(r["id"]) for r in (job_res.data or [])]

    # 6. Sample placement officer contacts seeded by demo data
    # Matches contacts with source='seed' and synthetic TPO emails/names
    ct_res = client.table("contacts").select("id, email, name, source").eq("source", "seed").execute()
    demo_contact_ids = []
    for c in ct_res.data or []:
        email = (c.get("email") or "").lower()
        name = (c.get("name") or "").lower()
        if (
            "synthetic" in name
            or "demo" in name
            or "synthetic-tpo" in email
            or "demo-tpo" in email
            or "demo-placement" in email
        ):
            demo_contact_ids.append(str(c["id"]))

    # Also contact_sources for those contacts
    contact_source_ids = []
    if demo_contact_ids:
        src_res = client.table("contact_sources").select("id").in_("contact_id", demo_contact_ids).execute()
        contact_source_ids = [str(r["id"]) for r in (src_res.data or [])]

    return {
        "student_records": student_record_ids,
        "campus_hiring": campus_hiring_ids,
        "batch_sharing": batch_sharing_ids,
        "internships": internship_ids,
        "jobs": job_ids,
        "contacts": demo_contact_ids,
        "contact_sources": contact_source_ids,
    }


def purge_demo_data(client: Optional[Client] = None, confirm: bool = False) -> Dict[str, int]:
    """Purges demo data if confirm=True; otherwise returns preview counts."""
    cli = client or get_supabase_client()
    data = scan_demo_data(cli)

    counts = {k: len(v) for k, v in data.items()}

    if not confirm:
        return counts

    # Execute deletions in child-to-parent order to respect foreign key constraints
    deleted = {}

    # 1. contact_sources
    if data["contact_sources"]:
        for cid in data["contact_sources"]:
            cli.table("contact_sources").delete().eq("id", cid).execute()
    deleted["contact_sources"] = len(data["contact_sources"])

    # 2. contacts
    if data["contacts"]:
        for cid in data["contacts"]:
            cli.table("contacts").delete().eq("id", cid).execute()
    deleted["contacts"] = len(data["contacts"])

    # 3. internships
    if data["internships"]:
        for iid in data["internships"]:
            cli.table("internships").delete().eq("id", iid).execute()
    deleted["internships"] = len(data["internships"])

    # 4. jobs
    if data["jobs"]:
        for jid in data["jobs"]:
            cli.table("jobs").delete().eq("id", jid).execute()
    deleted["jobs"] = len(data["jobs"])

    # 5. campus_hiring
    if data["campus_hiring"]:
        for chid in data["campus_hiring"]:
            cli.table("campus_hiring").delete().eq("id", chid).execute()
    deleted["campus_hiring"] = len(data["campus_hiring"])

    # 6. batch_sharing
    if data["batch_sharing"]:
        for bsid in data["batch_sharing"]:
            cli.table("batch_sharing").delete().eq("id", bsid).execute()
    deleted["batch_sharing"] = len(data["batch_sharing"])

    # 7. student_records
    if data["student_records"]:
        # Delete in chunks
        for i in range(0, len(data["student_records"]), 25):
            chunk = data["student_records"][i : i + 25]
            for s_id in chunk:
                cli.table("student_records").delete().eq("id", s_id).execute()
    deleted["student_records"] = len(data["student_records"])

    return deleted


def main() -> int:
    parser = argparse.ArgumentParser(description="Purge demo data from database.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm deletion of all demo data rows",
    )
    args = parser.parse_args()

    cli = get_supabase_client()
    counts = scan_demo_data(cli)

    print("==================================================")
    print("           Purge Demo Data Scan                   ")
    print("==================================================")
    print(f"student_records (is_demo_data=true): {len(counts['student_records'])}")
    print(f"campus_hiring (demo profiles):       {len(counts['campus_hiring'])}")
    print(f"batch_sharing (demo profiles):       {len(counts['batch_sharing'])}")
    print(f"internships (synthetic seed):        {len(counts['internships'])}")
    print(f"jobs (synthetic seed):               {len(counts['jobs'])}")
    print(f"sample contacts (synthetic seed):    {len(counts['contacts'])}")
    print(f"contact_sources (provenance):        {len(counts['contact_sources'])}")
    print("--------------------------------------------------")

    if not args.yes:
        print("[WARNING] Dry-run only. To delete these rows, re-run with --yes:")
        print("          python scripts/purge_demo_data.py --yes")
        return 0

    deleted = purge_demo_data(cli, confirm=True)
    print(f"[SUCCESS] Purged demo rows: {deleted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
