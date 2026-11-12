#!/usr/bin/env python3
"""
Seed CSV data loader for colleges, companies, college_domains, and sample contacts.
Loads data/seed/*.csv by name-to-id lookup idempotently (matching normalized names).
Tagged with source='seed' and source_url without creating duplicates of rows already imported.
Reports rows added, matched, and skipped for each seed step.
"""

import csv
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add apps/api to path
api_root = Path(__file__).resolve().parent.parent
if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))

from supabase import Client  # noqa: E402

from app.auth.college_resolution import get_registrable_root, is_freemail_domain  # noqa: E402
from app.db.supabase import get_supabase_client  # noqa: E402

SEED_DIR = api_root.parent.parent / "data" / "seed"


def load_colleges_csv(client: Client, csv_path: Optional[Path] = None) -> Dict[str, Any]:
    target = csv_path or (SEED_DIR / "colleges.csv")
    if not target.exists():
        return {"added": 0, "matched": 0, "skipped": 0, "college_map": {}}

    res = client.table("colleges").select("id, name, city").execute()
    colleges_map: Dict[str, str] = {c["name"].strip().lower(): str(c["id"]) for c in (res.data or [])}

    added = 0
    matched = 0
    skipped = 0

    with open(target, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_name = (row.get("name") or "").strip()
            if not raw_name:
                skipped += 1
                continue
            norm = raw_name.lower()
            city = (row.get("city") or "Mumbai").strip()
            placement_url = (row.get("placement_url") or row.get("source_url") or "").strip() or None

            if norm in colleges_map:
                matched += 1
                cid = colleges_map[norm]
                if placement_url:
                    try:
                        client.table("colleges").update({"placement_url": placement_url}).eq("id", cid).execute()
                    except Exception:
                        pass
            else:
                cid = str(uuid.uuid4())
                payload = {
                    "id": cid,
                    "name": raw_name,
                    "city": city,
                }
                if placement_url:
                    payload["placement_url"] = placement_url
                client.table("colleges").insert(payload).execute()
                colleges_map[norm] = cid
                added += 1

    return {"added": added, "matched": matched, "skipped": skipped, "college_map": colleges_map}


def load_companies_csv(client: Client, csv_path: Optional[Path] = None) -> Dict[str, Any]:
    target = csv_path or (SEED_DIR / "companies.csv")
    if not target.exists():
        return {"added": 0, "matched": 0, "skipped": 0, "company_map": {}}

    res = client.table("companies").select("id, name, industry, category").execute()
    companies_map: Dict[str, str] = {c["name"].strip().lower(): str(c["id"]) for c in (res.data or [])}

    added = 0
    matched = 0
    skipped = 0

    with open(target, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_name = (row.get("name") or "").strip()
            if not raw_name:
                skipped += 1
                continue
            norm = raw_name.lower()
            category = (row.get("category") or "").strip() or None
            industry = (row.get("industry") or "").strip() or None

            if norm in companies_map:
                matched += 1
                cid = companies_map[norm]
                update_fields = {}
                if category:
                    update_fields["category"] = category
                if industry:
                    update_fields["industry"] = industry
                if update_fields:
                    client.table("companies").update(update_fields).eq("id", cid).execute()
            else:
                cid = str(uuid.uuid4())
                payload = {
                    "id": cid,
                    "name": raw_name,
                    "category": category,
                    "industry": industry,
                }
                client.table("companies").insert(payload).execute()
                companies_map[norm] = cid
                added += 1

    return {"added": added, "matched": matched, "skipped": skipped, "company_map": companies_map}


def load_college_domains_csv(
    client: Client,
    colleges_map: Dict[str, str],
    csv_path: Optional[Path] = None,
) -> Dict[str, Any]:
    target = csv_path or (SEED_DIR / "college_domains.csv")
    if not target.exists():
        return {"added": 0, "matched": 0, "skipped": 0}

    # Fetch existing college domains
    dom_res = client.table("college_domains").select("id, college_id, domain").execute()
    domains_map = {d["domain"].strip().lower(): str(d["id"]) for d in (dom_res.data or []) if d.get("domain")}

    added = 0
    matched = 0
    skipped = 0

    with open(target, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            college_name = (row.get("college_name") or "").strip()
            raw_domain = (row.get("domain") or "").strip().lower()
            source_url = (row.get("source_url") or "").strip()
            kind = (row.get("kind") or "unknown").strip().lower()
            evidence = (row.get("evidence") or "").strip()
            conf_str = (row.get("confidence") or "1.0").strip()

            if not source_url or not college_name or not raw_domain or is_freemail_domain(raw_domain):
                skipped += 1
                continue

            domain = get_registrable_root(raw_domain)
            college_id = colleges_map.get(college_name.lower()) or (row.get("college_id") or "").strip()
            if not college_id:
                skipped += 1
                continue

            try:
                confidence = float(conf_str)
            except ValueError:
                confidence = 1.0

            if domain in domains_map:
                matched += 1
                rec_id = domains_map[domain]
                client.table("college_domains").update(
                    {
                        "source_url": source_url,
                        "evidence": evidence or None,
                        "confidence": confidence,
                    }
                ).eq("id", rec_id).execute()
            else:
                new_id = str(uuid.uuid4())
                client.table("college_domains").insert(
                    {
                        "id": new_id,
                        "college_id": college_id,
                        "domain": domain,
                        "kind": kind if kind in ("student", "staff", "unknown") else "unknown",
                        "source_url": source_url,
                        "evidence": evidence or None,
                        "confidence": confidence,
                    }
                ).execute()
                domains_map[domain] = new_id
                added += 1

    return {"added": added, "matched": matched, "skipped": skipped}


def load_contacts_csv(
    client: Client,
    colleges_map: Dict[str, str],
    companies_map: Dict[str, str],
    csv_path: Optional[Path] = None,
) -> Dict[str, Any]:
    target = csv_path or (SEED_DIR / "contacts.csv")
    if not target.exists():
        return {"added": 0, "matched": 0, "skipped": 0}

    # Fetch existing contacts
    ct_res = client.table("contacts").select("id, name, email, linkedin_url, company_id, college_id").execute()
    existing_contacts: List[Dict[str, Any]] = ct_res.data or []

    added = 0
    matched = 0
    skipped = 0

    with open(target, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_name = (row.get("name") or "").strip()
            if not raw_name:
                skipped += 1
                continue

            title = (row.get("title") or "").strip() or None
            role_type = (row.get("role_type") or "other").strip()
            email = (row.get("email") or "").strip().lower() or None
            linkedin_url = (row.get("linkedin_url") or "").strip().lower() or None
            source_url = (row.get("source_url") or linkedin_url or email or "https://example.com/seed").strip()

            comp_name = (row.get("company_name") or "").strip().lower()
            coll_name = (row.get("college_name") or "").strip().lower()
            company_id = companies_map.get(comp_name) if comp_name else None
            college_id = colleges_map.get(coll_name) if coll_name else None

            # Deduplication: match on linkedin_url, email, or (normalized name + company/college)
            matched_contact = None
            for ec in existing_contacts:
                if linkedin_url and ec.get("linkedin_url") and ec["linkedin_url"].lower() == linkedin_url:
                    matched_contact = ec
                    break
                if email and ec.get("email") and ec["email"].lower() == email:
                    matched_contact = ec
                    break
                if (
                    company_id
                    and ec.get("company_id") == company_id
                    and ec.get("name", "").strip().lower() == raw_name.lower()
                ):
                    matched_contact = ec
                    break
                if (
                    college_id
                    and ec.get("college_id") == college_id
                    and ec.get("name", "").strip().lower() == raw_name.lower()
                ):
                    matched_contact = ec
                    break

            payload = {
                "name": raw_name,
                "title": title,
                "role_type": role_type
                if role_type in ("campus_recruiter", "placement_officer", "hr", "other")
                else "other",
                "email": email,
                "linkedin_url": linkedin_url,
                "company_id": company_id,
                "college_id": college_id,
                "source": "seed",
                "source_url": source_url,
                "confidence": 1.0,
            }

            if matched_contact:
                matched += 1
                contact_id = str(matched_contact["id"])
                client.table("contacts").update(payload).eq("id", contact_id).execute()
            else:
                added += 1
                contact_id = str(uuid.uuid4())
                payload["id"] = contact_id
                client.table("contacts").insert(payload).execute()
                existing_contacts.append(payload)

            # Upsert provenance in contact_sources
            src_res = (
                client.table("contact_sources").select("id").eq("contact_id", contact_id).eq("source", "seed").execute()
            )
            if not (src_res.data and len(src_res.data) > 0):
                client.table("contact_sources").insert(
                    {
                        "id": str(uuid.uuid4()),
                        "contact_id": contact_id,
                        "source": "seed",
                        "source_url": source_url,
                        "confidence": 1.0,
                        "unverified": False,
                        "note": "synthetic",
                    }
                ).execute()

    return {"added": added, "matched": matched, "skipped": skipped}


def seed_all_csvs(client: Optional[Client] = None) -> Dict[str, Dict[str, int]]:
    cli = client or get_supabase_client()
    print("Loading colleges from CSV...")
    c_res = load_colleges_csv(cli)
    print(f"Colleges: added={c_res['added']}, matched={c_res['matched']}, skipped={c_res['skipped']}")

    print("Loading companies from CSV...")
    comp_res = load_companies_csv(cli)
    print(f"Companies: added={comp_res['added']}, matched={comp_res['matched']}, skipped={comp_res['skipped']}")

    print("Loading college domains from CSV...")
    dom_res = load_college_domains_csv(cli, colleges_map=c_res["college_map"])
    print(f"College Domains: added={dom_res['added']}, matched={dom_res['matched']}, skipped={dom_res['skipped']}")

    print("Loading sample contacts from CSV...")
    ct_res = load_contacts_csv(cli, colleges_map=c_res["college_map"], companies_map=comp_res["company_map"])
    print(f"Sample Contacts: added={ct_res['added']}, matched={ct_res['matched']}, skipped={ct_res['skipped']}")

    return {
        "colleges": {"added": c_res["added"], "matched": c_res["matched"], "skipped": c_res["skipped"]},
        "companies": {"added": comp_res["added"], "matched": comp_res["matched"], "skipped": comp_res["skipped"]},
        "college_domains": {"added": dom_res["added"], "matched": dom_res["matched"], "skipped": dom_res["skipped"]},
        "contacts": {"added": ct_res["added"], "matched": ct_res["matched"], "skipped": ct_res["skipped"]},
    }


if __name__ == "__main__":
    report = seed_all_csvs()
    print("\nSummary Report:")
    for k, v in report.items():
        print(f"  {k}: added={v['added']}, matched={v['matched']}, skipped={v['skipped']}")
