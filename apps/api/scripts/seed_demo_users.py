"""
Seed script for real demo users.
Idempotently creates or updates real Supabase Auth users for each role:
- placement_officer
- company
- recruiter
- student

Passwords are read from the environment variable DEMO_USER_PASSWORD (or role-specific env vars).
Never commit passwords.
"""

import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add apps/api to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from supabase import Client

from app.config import settings
from app.db.supabase import get_supabase_client
from app.logger import logger


def seed_demo_users(
    client: Optional[Client] = None,
    demo_password: Optional[str] = None,
) -> Dict[str, Any]:
    """Idempotently seeds real demo users in Supabase Auth and matching profiles."""
    cli = client or get_supabase_client()
    default_password = (
        demo_password
        or os.environ.get("DEMO_USER_PASSWORD")
        or settings.DEMO_USER_PASSWORD
    )

    if not default_password:
        raise ValueError(
            "DEMO_USER_PASSWORD environment variable must be set to seed demo users. "
            "Pass a secure random value, e.g. DEMO_USER_PASSWORD='...'"
        )

    # 1. Resolve or create a real demo college (real UUID)
    coll_res = (
        cli.table("colleges")
        .select("id, name")
        .ilike("name", "%St. Xavier%Demo%")
        .execute()
    )
    if coll_res.data and len(coll_res.data) > 0:
        demo_college_id = str(coll_res.data[0]["id"])
    else:
        # Check any existing college first
        any_coll = cli.table("colleges").select("id, name").limit(1).execute()
        if any_coll.data and len(any_coll.data) > 0:
            demo_college_id = str(any_coll.data[0]["id"])
        else:
            demo_college_id = str(uuid.uuid4())
            cli.table("colleges").insert(
                {
                    "id": demo_college_id,
                    "name": "St. Xavier's College (Autonomous), Mumbai",
                    "city": "Mumbai",
                    "state": "Maharashtra",
                }
            ).execute()

    # 2. Resolve or create a real demo company (real UUID)
    comp_res = (
        cli.table("companies")
        .select("id, name")
        .ilike("name", "%Tata Consultancy%Demo%")
        .execute()
    )
    if comp_res.data and len(comp_res.data) > 0:
        demo_company_id = str(comp_res.data[0]["id"])
    else:
        any_comp = cli.table("companies").select("id, name").limit(1).execute()
        if any_comp.data and len(any_comp.data) > 0:
            demo_company_id = str(any_comp.data[0]["id"])
        else:
            demo_company_id = str(uuid.uuid4())
            cli.table("companies").insert(
                {
                    "id": demo_company_id,
                    "name": "Tata Consultancy Services (Demo)",
                    "city": "Mumbai",
                }
            ).execute()

    demo_specs = [
        {
            "role": "placement_officer",
            "email": "demo-officer@example.com",
            "display_name": "Prof. Sunita Patil",
            "college_id": demo_college_id,
            "company_id": None,
        },
        {
            "role": "company",
            "email": "demo-company@example.com",
            "display_name": "Pooja Sharma",
            "college_id": None,
            "company_id": demo_company_id,
        },
        {
            "role": "recruiter",
            "email": "demo-recruiter@example.com",
            "display_name": "Karan Mehta",
            "college_id": None,
            "company_id": None,
        },
        {
            "role": "student",
            "email": "demo-student@example.com",
            "display_name": "Riya Sharma",
            "college_id": demo_college_id,
            "company_id": None,
        },
    ]

    # Pre-fetch existing auth users list
    existing_users = []
    try:
        users_resp = cli.auth.admin.list_users()
        existing_users = getattr(users_resp, "users", users_resp or [])
    except Exception as exc:
        logger.warning(f"Could not list existing auth users: {exc}")

    results = []

    for spec in demo_specs:
        email = spec["email"]
        role = spec["role"]
        display_name = spec["display_name"]
        pwd = (
            os.environ.get(f"DEMO_PASSWORD_{role.upper()}")
            or default_password
        )

        matched_user = next(
            (u for u in existing_users if getattr(u, "email", None) == email),
            None,
        )

        user_id = None
        if matched_user:
            user_id = str(matched_user.id)
            logger.info(f"Updating existing demo auth user {email} ({user_id})")
            try:
                cli.auth.admin.update_user_by_id(
                    user_id,
                    {
                        "password": pwd,
                        "email_confirm": True,
                        "user_metadata": {
                            "role": role,
                            "display_name": display_name,
                            "is_demo": True,
                        },
                    },
                )
            except Exception as exc:
                logger.warning(f"Error updating user {email}: {exc}")
        else:
            logger.info(f"Creating new demo auth user {email}")
            try:
                created = cli.auth.admin.create_user(
                    {
                        "email": email,
                        "password": pwd,
                        "email_confirm": True,
                        "user_metadata": {
                            "role": role,
                            "display_name": display_name,
                            "is_demo": True,
                        },
                    }
                )
                user_id = str(
                    getattr(created, "user", created).id
                )
            except Exception as exc:
                logger.error(f"Failed to create demo auth user {email}: {exc}")
                raise

        # Upsert profile matching auth user ID
        profile_data = {
            "id": user_id,
            "email": email,
            "role": role,
            "display_name": display_name,
            "college_id": spec["college_id"],
            "company_id": spec["company_id"],
            "is_demo": True,
        }
        cli.table("profiles").upsert(profile_data, on_conflict="id").execute()

        # For student role, ensure students table row exists
        if role == "student":
            stu_check = (
                cli.table("students")
                .select("id")
                .eq("profile_id", user_id)
                .execute()
            )
            if not stu_check.data:
                cli.table("students").insert(
                    {
                        "id": str(uuid.uuid4()),
                        "profile_id": user_id,
                        "full_name": display_name,
                        "college_id": spec["college_id"],
                        "batch_year": 2027,
                        "degree": "B.Tech",
                    }
                ).execute()

        results.append({"role": role, "email": email, "user_id": user_id})

    logger.info(f"Successfully seeded {len(results)} demo users.")
    return {
        "status": "success",
        "demo_college_id": demo_college_id,
        "demo_company_id": demo_company_id,
        "users": results,
    }


if __name__ == "__main__":
    try:
        res = seed_demo_users()
        print(f"Seed complete: {res}")
    except Exception as e:
        print(f"Seed failed: {e}", file=sys.stderr)
        sys.exit(1)
