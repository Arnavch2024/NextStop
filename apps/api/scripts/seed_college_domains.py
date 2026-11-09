"""
Seed script for college_domains.
Reads data/seed/college_domains.csv and populates the college_domains table in Supabase.
Skips any row without a valid source_url.
"""

import csv
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add apps/api to path so app modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from supabase import Client

from app.db.supabase import get_supabase_client
from app.logger import logger

CSV_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "seed" / "college_domains.csv"


def seed_college_domains(
    csv_path: Optional[Path] = None,
    client: Optional[Client] = None,
) -> Dict[str, Any]:
    """Reads college_domains.csv and seeds the college_domains table.

    Only rows with valid non-empty source_url are included.
    """
    target_csv = csv_path or CSV_PATH
    if not target_csv.exists():
        logger.error(f"Seed CSV not found at {target_csv}")
        return {"imported": 0, "skipped": 0, "reasons": [f"File not found: {target_csv}"]}

    cli = client or get_supabase_client()

    # Pre-fetch existing colleges into a lookup map: normalized name -> id
    coll_res = cli.table("colleges").select("id, name").execute()
    colleges_map: Dict[str, str] = {}
    for c in coll_res.data or []:
        colleges_map[c["name"].strip().lower()] = str(c["id"])

    imported = 0
    skipped = 0
    reasons: List[str] = []

    with open(target_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=2):
            college_name = (row.get("college_name") or "").strip()
            domain = (row.get("domain") or "").strip().lower()
            kind = (row.get("kind") or "").strip().lower()
            source_url = (row.get("source_url") or "").strip()

            # Validation 1: Skip if source_url is missing
            if not source_url:
                skipped += 1
                reasons.append(f"Row {idx}: Missing source_url for domain '{domain}'")
                continue

            # Validation 2: Missing required fields
            if not college_name or not domain:
                skipped += 1
                reasons.append(f"Row {idx}: Missing college_name or domain")
                continue

            # Validation 3: Check kind
            if kind not in ("student", "staff"):
                skipped += 1
                reasons.append(f"Row {idx}: Invalid kind '{kind}' for domain '{domain}'")
                continue

            # Find or create college
            coll_key = college_name.lower()
            college_id = colleges_map.get(coll_key)
            if not college_id:
                # Attempt to match by partial or create college row
                try:
                    new_coll = (
                        cli.table("colleges")
                        .insert({"name": college_name, "city": "Mumbai", "placement_url": source_url})
                        .execute()
                    )
                    if new_coll.data and len(new_coll.data) > 0:
                        college_id = str(new_coll.data[0]["id"])
                        colleges_map[coll_key] = college_id
                except Exception as exc:
                    logger.warning(f"Could not auto-create college {college_name}: {exc}")

            if not college_id:
                skipped += 1
                reasons.append(f"Row {idx}: College '{college_name}' not found in database")
                continue

            # Upsert into college_domains
            payload = {
                "college_id": college_id,
                "domain": domain,
                "kind": kind,
                "source_url": source_url,
            }
            try:
                # Upsert by domain
                cli.table("college_domains").upsert(payload, on_conflict="domain").execute()
                imported += 1
            except Exception as exc:
                skipped += 1
                reasons.append(f"Row {idx}: DB error for domain '{domain}': {exc}")

    logger.info(f"College domains seed finished: {imported} imported, {skipped} skipped.")
    return {"imported": imported, "skipped": skipped, "reasons": reasons}


if __name__ == "__main__":
    result = seed_college_domains()
    print(f"Imported: {result['imported']}, Skipped: {result['skipped']}")
    if result["reasons"]:
        print("Reasons:")
        for r in result["reasons"]:
            print(f" - {r}")
