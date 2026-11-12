#!/usr/bin/env python3
"""
Stand-alone, idempotent demo data seeder.
Run manually; never exposed as an API endpoint.

Creates clearly synthetic demo data with is_demo_data=true / demo profile associations:
1. ~60 synthetic student_records at demo officer's college (University of Mumbai):
   - Batches 2027 and 2028
   - Branches: Computer Engineering, Information Technology, AI & Data Science, Electronics Engineering, Mechanical Engineering
   - Statuses: in_college, internship, full_time, not_placed
   - Varied CGPA and percentages
   - Obviously fake names; NO email, phone, Aadhaar, or documents
   - Batch sharing enabled for batch 2027 (and some opted-out records)
2. ~15 synthetic student_records at a second college (JBIMS):
   - Batches 2027 and 2028
   - Branches: Finance, Marketing, Operations (MBA)
   - Multiple MBA (Finance) records with CGPA > 9.0
   - Batch sharing enabled for batch 2027
3. Campus hiring rows for demo company (JP Morgan Chase Global Technology):
   - Multiple colleges (University of Mumbai, IIT Bombay, VJTI, JBIMS)
   - 2-3 cycles (2024, 2025, 2026)
   - Interesting offer bands: zero-offer (0 offers -> -1 pt), 5-9 offers (+1 pt), >20 offers (+3 pts)
4. Synthetic internships and jobs for demo student record
5. Sample placement officer contacts for recruiter queries (source='seed', note='synthetic')

Deterministic UUIDs ensure 100% idempotency across repeated runs.
"""

import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add apps/api to path
api_root = Path(__file__).resolve().parent.parent
if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))

from supabase import Client  # noqa: E402

from app.db.supabase import get_supabase_client  # noqa: E402

# Deterministic namespace for demo data
DEMO_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "recruiting.demo.wildcatter")


def resolve_demo_entities(client: Client) -> Dict[str, Any]:
    """Resolves demo profile IDs and college/company UUIDs."""
    # 1. Demo Officer Profile
    officer_res = (
        client.table("profiles")
        .select("id, college_id, display_name")
        .eq("role", "placement_officer")
        .eq("is_demo", True)
        .execute()
    )
    if not (officer_res.data and len(officer_res.data) > 0):
        raise RuntimeError("Demo placement officer profile not found. Run seed_demo_users.py first.")
    demo_officer = officer_res.data[0]
    officer_id = str(demo_officer["id"])
    demo_college_id = str(demo_officer.get("college_id"))

    # Fallback/verify demo college
    if not demo_college_id or demo_college_id == "None":
        coll_res = client.table("colleges").select("id").ilike("name", "%University of Mumbai%").execute()
        if coll_res.data and len(coll_res.data) > 0:
            demo_college_id = str(coll_res.data[0]["id"])
        else:
            first_coll = client.table("colleges").select("id").limit(1).execute()
            demo_college_id = str(first_coll.data[0]["id"])

    # 2. Second College (JBIMS or VJTI)
    sec_res = client.table("colleges").select("id, name").ilike("name", "%Jamnalal Bajaj%").execute()
    if sec_res.data and len(sec_res.data) > 0:
        second_college_id = str(sec_res.data[0]["id"])
    else:
        sec_res2 = client.table("colleges").select("id, name").ilike("name", "%VJTI%").execute()
        second_college_id = str(sec_res2.data[0]["id"]) if sec_res2.data else demo_college_id

    # 3. Other Colleges for Campus Hiring
    iitb_res = client.table("colleges").select("id").ilike("name", "%IIT Bombay%").execute()
    iitb_id = str(iitb_res.data[0]["id"]) if iitb_res.data else demo_college_id

    vjti_res = client.table("colleges").select("id").ilike("name", "%VJTI%").execute()
    vjti_id = str(vjti_res.data[0]["id"]) if vjti_res.data else demo_college_id

    # 4. Demo Company Profile
    comp_prof_res = (
        client.table("profiles")
        .select("id, company_id, display_name")
        .eq("role", "company")
        .eq("is_demo", True)
        .execute()
    )
    if not (comp_prof_res.data and len(comp_prof_res.data) > 0):
        raise RuntimeError("Demo company profile not found. Run seed_demo_users.py first.")
    demo_comp_prof = comp_prof_res.data[0]
    company_profile_id = str(demo_comp_prof["id"])
    demo_company_id = str(demo_comp_prof.get("company_id"))

    if not demo_company_id or demo_company_id == "None":
        comp_res = client.table("companies").select("id").ilike("name", "%JP Morgan%").execute()
        demo_company_id = str(comp_res.data[0]["id"]) if comp_res.data else str(uuid.uuid4())

    # 5. Demo Student Profile
    stud_prof_res = (
        client.table("profiles").select("id, display_name").eq("role", "student").eq("is_demo", True).execute()
    )
    student_profile_id = str(stud_prof_res.data[0]["id"]) if stud_prof_res.data else None

    # Student row in students table
    student_id = None
    if student_profile_id:
        st_res = client.table("students").select("id").eq("profile_id", student_profile_id).execute()
        if st_res.data and len(st_res.data) > 0:
            student_id = str(st_res.data[0]["id"])

    return {
        "officer_profile_id": officer_id,
        "demo_college_id": demo_college_id,
        "second_college_id": second_college_id,
        "iitb_college_id": iitb_id,
        "vjti_college_id": vjti_id,
        "company_profile_id": company_profile_id,
        "demo_company_id": demo_company_id,
        "student_profile_id": student_profile_id,
        "student_id": student_id,
    }


def seed_demo_student_records(client: Client, entities: Dict[str, Any]) -> Dict[str, int]:
    """
    Seeds ~60 synthetic records for demo officer's college and ~15 at second college.
    Clearly synthetic names, no emails, no phones, no documents.
    """
    officer_id = entities["officer_profile_id"]
    demo_college_id = entities["demo_college_id"]
    second_college_id = entities["second_college_id"]
    demo_student_profile_id = entities["student_profile_id"]

    branches = [
        "Computer Engineering",
        "Information Technology",
        "AI & Data Science",
        "Electronics Engineering",
        "Mechanical Engineering",
    ]
    statuses = ["in_college", "internship", "full_time", "not_placed"]

    records: List[Dict[str, Any]] = []

    # 1. 60 records for Demo Officer College (University of Mumbai)
    for i in range(1, 61):
        rec_id = str(uuid.uuid5(DEMO_NAMESPACE, f"demo-officer-student-{i}"))
        batch = 2027 if i <= 30 else 2028
        branch = branches[(i - 1) % len(branches)]
        status = statuses[(i - 1) % len(statuses)]

        # Varied scores: some cgpa10 (6.8 to 9.8), some percentage (68.0 to 94.0)
        if i % 3 == 0:
            score_scale = "percentage"
            score_value = round(68.0 + ((i * 1.7) % 27.0), 1)
        else:
            score_scale = "cgpa10"
            score_value = round(6.5 + ((i * 0.31) % 3.4), 2)

        # Opt-out 2 students in batch 2027 for visibility testing
        opted_out = batch == 2027 and i in (7, 13)

        # Claim one record for the demo student
        claimed_by = demo_student_profile_id if i == 1 else None

        records.append(
            {
                "id": rec_id,
                "college_id": demo_college_id,
                "full_name": f"Synthetic Candidate MU-{i:02d}",
                "email": None,  # Strictly NO email
                "batch_year": batch,
                "branch": branch,
                "degree": "B.Tech",
                "score_value": score_value,
                "score_scale": score_scale,
                "current_status": status,
                "resume_ref": None,  # Strictly NO document
                "claimed_by_profile_id": claimed_by,
                "discoverable": False,
                "opted_out": opted_out,
                "is_demo_data": True,
                "created_by_profile_id": officer_id,
            }
        )

    # 2. 15 records for Second College (JBIMS) with MBA (Finance) CGPA > 9.0
    mba_branches = ["Finance", "Marketing", "Operations"]
    for j in range(1, 16):
        rec_id = str(uuid.uuid5(DEMO_NAMESPACE, f"demo-second-college-student-{j}"))
        batch = 2027 if j <= 10 else 2028
        branch = "Finance" if j <= 8 else mba_branches[j % len(mba_branches)]
        status = statuses[(j - 1) % len(statuses)]

        # Specific MBA Finance students with CGPA > 9.0
        if j in (1, 2, 3, 4):
            score_value = round(9.1 + (j * 0.2), 2)  # 9.3, 9.5, 9.7, 9.9
            score_scale = "cgpa10"
        else:
            score_value = round(7.2 + ((j * 0.4) % 2.5), 2)
            score_scale = "cgpa10"

        records.append(
            {
                "id": rec_id,
                "college_id": second_college_id,
                "full_name": f"Synthetic Scholar JBIMS-{j:02d}",
                "email": None,  # Strictly NO email
                "batch_year": batch,
                "branch": branch,
                "degree": "MBA",
                "score_value": score_value,
                "score_scale": score_scale,
                "current_status": status,
                "resume_ref": None,
                "claimed_by_profile_id": None,
                "discoverable": False,
                "opted_out": False,
                "is_demo_data": True,
                "created_by_profile_id": officer_id,
            }
        )

    # Upsert student records in efficient batches
    for i in range(0, len(records), 25):
        chunk = records[i : i + 25]
        client.table("student_records").upsert(chunk).execute()

    return {"mu_students": 60, "second_college_students": 15, "total": len(records)}


def seed_demo_batch_sharing(client: Client, entities: Dict[str, Any]) -> int:
    """Configures batch sharing for demo colleges."""
    officer_id = entities["officer_profile_id"]
    demo_college_id = entities["demo_college_id"]
    second_college_id = entities["second_college_id"]

    shares = [
        # Demo College: batch 2027 shared, 2028 not shared
        {
            "id": str(uuid.uuid5(DEMO_NAMESPACE, f"demo-batch-share-{demo_college_id}-2027")),
            "college_id": demo_college_id,
            "batch_year": 2027,
            "shared_with_recruiters": True,
            "set_by_profile_id": officer_id,
        },
        {
            "id": str(uuid.uuid5(DEMO_NAMESPACE, f"demo-batch-share-{demo_college_id}-2028")),
            "college_id": demo_college_id,
            "batch_year": 2028,
            "shared_with_recruiters": False,
            "set_by_profile_id": officer_id,
        },
        # Second College: batch 2027 shared
        {
            "id": str(uuid.uuid5(DEMO_NAMESPACE, f"demo-batch-share-{second_college_id}-2027")),
            "college_id": second_college_id,
            "batch_year": 2027,
            "shared_with_recruiters": True,
            "set_by_profile_id": officer_id,
        },
    ]

    count = 0
    for s in shares:
        exist = (
            client.table("batch_sharing")
            .select("id")
            .eq("college_id", s["college_id"])
            .eq("batch_year", s["batch_year"])
            .execute()
        )
        if exist.data and len(exist.data) > 0:
            client.table("batch_sharing").update(s).eq("id", exist.data[0]["id"]).execute()
        else:
            client.table("batch_sharing").insert(s).execute()
        count += 1

    return count


def seed_demo_campus_hiring(client: Client, entities: Dict[str, Any]) -> int:
    """
    Seeds campus hiring records for demo company:
    - 2-3 cycles (2024, 2025, 2026)
    - Different colleges (University of Mumbai, IIT Bombay, VJTI, JBIMS)
    - Diverse offer counts (zero-offer -> -1 pt, 5-9 offers -> +1 pt, >20 offers -> +3 pts)
    """
    comp_prof_id = entities["company_profile_id"]
    company_id = entities["demo_company_id"]
    demo_college_id = entities["demo_college_id"]
    iitb_id = entities["iitb_college_id"]
    vjti_id = entities["vjti_college_id"]
    jbims_id = entities["second_college_id"]

    specs = [
        # 1. Zero-offer cycle -> -1 pt
        {
            "college_id": demo_college_id,
            "cycle_year": 2024,
            "type": "full_time",
            "students_interviewed": 14,
            "offers_made": 0,
        },
        # 2. 5-9 offers -> +1 pt (University of Mumbai 2025)
        {
            "college_id": demo_college_id,
            "cycle_year": 2025,
            "type": "full_time",
            "students_interviewed": 28,
            "offers_made": 8,
        },
        # 3. Summer internship cycle at University of Mumbai
        {
            "college_id": demo_college_id,
            "cycle_year": 2025,
            "type": "internship",
            "students_interviewed": 20,
            "offers_made": 6,
        },
        # 4. 5-9 offers at VJTI
        {
            "college_id": vjti_id,
            "cycle_year": 2025,
            "type": "full_time",
            "students_interviewed": 22,
            "offers_made": 7,
        },
        # 5. >20 offers at IIT Bombay -> +3 pts
        {
            "college_id": iitb_id,
            "cycle_year": 2026,
            "type": "full_time",
            "students_interviewed": 85,
            "offers_made": 24,
        },
        # 6. Internship cycle at IIT Bombay
        {
            "college_id": iitb_id,
            "cycle_year": 2026,
            "type": "internship",
            "students_interviewed": 45,
            "offers_made": 14,
        },
        # 7. 5-9 offers at JBIMS
        {
            "college_id": jbims_id,
            "cycle_year": 2025,
            "type": "full_time",
            "students_interviewed": 18,
            "offers_made": 5,
        },
    ]

    count = 0
    for sp in specs:
        rec_id = str(
            uuid.uuid5(
                DEMO_NAMESPACE,
                f"campus-hiring-{company_id}-{sp['college_id']}-{sp['cycle_year']}-{sp['type']}",
            )
        )
        payload = {
            "id": rec_id,
            "company_id": company_id,
            "college_id": sp["college_id"],
            "cycle_year": sp["cycle_year"],
            "type": sp["type"],
            "students_interviewed": sp["students_interviewed"],
            "offers_made": sp["offers_made"],
            "profile_id": comp_prof_id,
        }

        # Check existing by unique constraint (company_id, college_id, cycle_year, type)
        exist = (
            client.table("campus_hiring")
            .select("id")
            .eq("company_id", company_id)
            .eq("college_id", sp["college_id"])
            .eq("cycle_year", sp["cycle_year"])
            .eq("type", sp["type"])
            .execute()
        )
        if exist.data and len(exist.data) > 0:
            client.table("campus_hiring").update(payload).eq("id", exist.data[0]["id"]).execute()
        else:
            client.table("campus_hiring").insert(payload).execute()
        count += 1

    return count


def seed_demo_internships_and_jobs(client: Client, entities: Dict[str, Any]) -> Dict[str, int]:
    """Seeds synthetic internships and jobs for the demo student profile."""
    student_id = entities.get("student_id")
    student_profile_id = entities.get("student_profile_id")
    demo_company_id = entities["demo_company_id"]

    if not student_id or not student_profile_id:
        return {"internships": 0, "jobs": 0}

    # Synthetic internships
    internships = [
        {
            "id": str(uuid.uuid5(DEMO_NAMESPACE, f"demo-internship-1-{student_id}")),
            "student_id": student_id,
            "profile_id": student_profile_id,
            "company": "JP Morgan Chase Global Technology",
            "company_id": demo_company_id,
            "role": "Summer Technology Analyst",
            "start_date": "2024-05-15",
            "end_date": "2024-07-31",
            "duration_months": 2.5,
            "source": "seed",
            "confidence": 1.0,
        },
        {
            "id": str(uuid.uuid5(DEMO_NAMESPACE, f"demo-internship-2-{student_id}")),
            "student_id": student_id,
            "profile_id": student_profile_id,
            "company": "Tata Consultancy Services (Demo)",
            "role": "AI Research Intern",
            "start_date": "2025-05-01",
            "end_date": "2025-07-15",
            "duration_months": 2.5,
            "source": "seed",
            "confidence": 1.0,
        },
    ]

    for item in internships:
        exist = client.table("internships").select("id").eq("id", item["id"]).execute()
        if exist.data and len(exist.data) > 0:
            client.table("internships").update(item).eq("id", item["id"]).execute()
        else:
            client.table("internships").insert(item).execute()

    # Synthetic jobs
    jobs = [
        {
            "id": str(uuid.uuid5(DEMO_NAMESPACE, f"demo-job-1-{student_id}")),
            "student_id": student_id,
            "profile_id": student_profile_id,
            "company": "Demo FinTech Labs Mumbai",
            "role": "Associate Software Engineer",
            "start_date": "2026-01-10",
            "end_date": None,  # Current
            "duration_months": 4.0,
            "source": "seed",
            "confidence": 1.0,
        }
    ]

    for j in jobs:
        exist = client.table("jobs").select("id").eq("id", j["id"]).execute()
        if exist.data and len(exist.data) > 0:
            client.table("jobs").update(j).eq("id", j["id"]).execute()
        else:
            client.table("jobs").insert(j).execute()

    return {"internships": len(internships), "jobs": len(jobs)}


def seed_demo_sample_contacts(client: Client, entities: Dict[str, Any]) -> int:
    """Seeds synthetic placement officer contacts for recruiter searches."""
    demo_college_id = entities["demo_college_id"]
    second_college_id = entities["second_college_id"]
    vjti_id = entities["vjti_college_id"]

    sample_officers = [
        {
            "college_id": demo_college_id,
            "name": "Prof. Synthetic Head - MU Placements",
            "title": "Head of Corporate Relations & Placements",
            "role_type": "placement_officer",
            "email": "synthetic-tpo@mu.ac.in",
            "source_url": "https://example.edu/demo-tpo-mu",
        },
        {
            "college_id": vjti_id,
            "name": "Dr. Demo Officer - VJTI TPO",
            "title": "Training & Placement Officer",
            "role_type": "placement_officer",
            "email": "demo-tpo@vjti.ac.in",
            "source_url": "https://example.edu/demo-tpo-vjti",
        },
        {
            "college_id": second_college_id,
            "name": "Prof. Sample Coordinator - JBIMS Placements",
            "title": "Placement Convenor (Corporate Admissions)",
            "role_type": "placement_officer",
            "email": "demo-placement@jbims.edu",
            "source_url": "https://example.edu/demo-tpo-jbims",
        },
    ]

    count = 0
    for ct in sample_officers:
        contact_id = str(uuid.uuid5(DEMO_NAMESPACE, f"demo-sample-contact-{ct['college_id']}"))
        payload = {
            "id": contact_id,
            "name": ct["name"],
            "title": ct["title"],
            "role_type": ct["role_type"],
            "email": ct["email"],
            "college_id": ct["college_id"],
            "company_id": None,
            "source": "seed",
            "source_url": ct["source_url"],
            "confidence": 1.0,
        }

        exist = client.table("contacts").select("id").eq("id", contact_id).execute()
        if exist.data and len(exist.data) > 0:
            client.table("contacts").update(payload).eq("id", contact_id).execute()
        else:
            client.table("contacts").insert(payload).execute()

        # Provenance in contact_sources
        src_res = client.table("contact_sources").select("id").eq("contact_id", contact_id).execute()
        if not (src_res.data and len(src_res.data) > 0):
            client.table("contact_sources").insert(
                {
                    "id": str(uuid.uuid5(DEMO_NAMESPACE, f"demo-contact-src-{contact_id}")),
                    "contact_id": contact_id,
                    "source": "seed",
                    "source_url": ct["source_url"],
                    "confidence": 1.0,
                    "unverified": False,
                    "note": "synthetic",
                }
            ).execute()
        count += 1

    return count


def seed_demo_data(client: Optional[Client] = None) -> Dict[str, Any]:
    """Top-level idempotent runner for all demo data generation."""
    cli = client or get_supabase_client()
    entities = resolve_demo_entities(cli)

    print("Seeding synthetic student_records...")
    student_report = seed_demo_student_records(cli, entities)

    print("Configuring demo batch_sharing...")
    batch_count = seed_demo_batch_sharing(cli, entities)

    print("Seeding demo campus_hiring rows...")
    campus_count = seed_demo_campus_hiring(cli, entities)

    print("Seeding demo internships & jobs...")
    work_report = seed_demo_internships_and_jobs(cli, entities)

    print("Seeding demo placement officer contacts...")
    contact_count = seed_demo_sample_contacts(cli, entities)

    summary = {
        "student_records": student_report["total"],
        "batch_sharing": batch_count,
        "campus_hiring": campus_count,
        "internships": work_report["internships"],
        "jobs": work_report["jobs"],
        "sample_contacts": contact_count,
    }
    print(f"\n[SUCCESS] Demo data seed complete: {summary}")
    return summary


if __name__ == "__main__":
    seed_demo_data()
