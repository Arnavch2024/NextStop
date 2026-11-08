import uuid
from typing import Any, Dict

from google.genai import types
from pydantic import ValidationError
from supabase import Client

from app.logger import logger
from app.models.db import (
    ALLOWED_TABLES,
    TABLE_VALIDATORS,
    ProfileRole,
    UserProfile,
)
from app.scoring.loader import recompute_score

UPSERT_RECORD_TOOL_NAME = "upsert_record"

UPSERT_RECORD_DECLARATION = types.FunctionDeclaration(
    name=UPSERT_RECORD_TOOL_NAME,
    description="Create or update a record in a structured table. Use for students, colleges, companies, contacts, education, internships, jobs, skills.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "table": types.Schema(
                type=types.Type.STRING,
                enum=list(ALLOWED_TABLES),
                description="The target table to upsert: 'students', 'colleges', 'companies', 'contacts', 'education', 'internships', 'jobs', or 'skills'",
            ),
            "data": types.Schema(
                type=types.Type.OBJECT,
                description="Key-value fields for the record matching the table schema",
            ),
        },
        required=["table", "data"],
    ),
)

UPSERT_RECORD_TOOL = types.Tool(function_declarations=[UPSERT_RECORD_DECLARATION])

SEARCH_DATA_LAKE_TOOL_NAME = "search_data_lake"
WEB_SEARCH_ENRICH_TOOL_NAME = "web_search_enrich"
UPSERT_CONTACT_TOOL_NAME = "upsert_contact"
DRAFT_OUTREACH_TOOL_NAME = "draft_outreach"

SEARCH_DATA_LAKE_DECLARATION = types.FunctionDeclaration(
    name=SEARCH_DATA_LAKE_TOOL_NAME,
    description="Search the shared contacts data lake first. Returns existing contacts matching the query and filters.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "query": types.Schema(
                type=types.Type.STRING,
                description="Free-text query (e.g. name, title, company name, college name)",
            ),
            "filters": types.Schema(
                type=types.Type.OBJECT,
                description="Optional structured filters: company_id, college_id, role_type",
            ),
            "include_sample": types.Schema(
                type=types.Type.BOOLEAN,
                description="Whether to include sample/seed data in results (defaults to false unless DEMO_SHOW_SAMPLE is enabled)",
            ),
        },
    ),
)

WEB_SEARCH_ENRICH_DECLARATION = types.FunctionDeclaration(
    name=WEB_SEARCH_ENRICH_TOOL_NAME,
    description="Search the public web to discover contacts or enrich company information. Only use when data lake results are thin. Never scrape LinkedIn.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "query": types.Schema(
                type=types.Type.STRING,
                description="Search query string",
            ),
            "extract_page_text": types.Schema(
                type=types.Type.BOOLEAN,
                description="Whether to fetch and extract page text from top non-LinkedIn result",
            ),
        },
        required=["query"],
    ),
)

UPSERT_CONTACT_DECLARATION = types.FunctionDeclaration(
    name=UPSERT_CONTACT_TOOL_NAME,
    description="Upsert a contact into the shared lake with deduplication, priority merge (web > user_said > seed), and provenance tracking. Conflicting user info routes to private list. Never store phone in lake.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "name": types.Schema(
                type=types.Type.STRING,
                description="Full name of the contact (required)",
            ),
            "company_id": types.Schema(
                type=types.Type.STRING,
                description="UUID of associated company",
            ),
            "college_id": types.Schema(
                type=types.Type.STRING,
                description="UUID of associated college",
            ),
            "title": types.Schema(
                type=types.Type.STRING,
                description="Job title or role",
            ),
            "role_type": types.Schema(
                type=types.Type.STRING,
                enum=["campus_recruiter", "placement_officer", "hr", "other"],
                description="Contact role type category",
            ),
            "email": types.Schema(
                type=types.Type.STRING,
                description="Professional email address",
            ),
            "linkedin_url": types.Schema(
                type=types.Type.STRING,
                description="Public LinkedIn profile URL",
            ),
            "source": types.Schema(
                type=types.Type.STRING,
                enum=["web", "user_said", "seed"],
                description="Provenance source of contact info",
            ),
            "source_url": types.Schema(
                type=types.Type.STRING,
                description="URL where contact was found",
            ),
            "phone": types.Schema(
                type=types.Type.STRING,
                description="Phone number (stored privately in caller's saved contacts only; never in lake)",
            ),
        },
        required=["name"],
    ),
)

DRAFT_OUTREACH_DECLARATION = types.FunctionDeclaration(
    name=DRAFT_OUTREACH_TOOL_NAME,
    description="Draft an outreach message (email or LinkedIn connection note) for a contact. NEVER sends messages over the network; stores as a private draft.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "contact_id": types.Schema(
                type=types.Type.STRING,
                description="UUID of the contact to draft outreach for",
            ),
            "channel": types.Schema(
                type=types.Type.STRING,
                enum=["email", "linkedin"],
                description="Outreach channel ('email' or 'linkedin')",
            ),
            "sender_context": types.Schema(
                type=types.Type.STRING,
                description="Optional additional context or note from the sender",
            ),
        },
        required=["contact_id", "channel"],
    ),
)


def get_tools_for_role(role: ProfileRole) -> list[types.Tool]:
    """
    Returns role-aware Gemini tool declarations.
    Students, Placement Officers, Companies, and Recruiters now have access to search & outreach tools
    alongside structured upserts (e.g. students discovering GCC recruiters in Mumbai).
    """
    return [
        types.Tool(
            function_declarations=[
                UPSERT_RECORD_DECLARATION,
                SEARCH_DATA_LAKE_DECLARATION,
                WEB_SEARCH_ENRICH_DECLARATION,
                UPSERT_CONTACT_DECLARATION,
                DRAFT_OUTREACH_DECLARATION,
            ]
        )
    ]


def handle_upsert(
    supabase_client: Client,
    user: UserProfile,
    table: str,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Executes a server-validated, ownership-enforced natural-key upsert on the whitelist of tables.
    Returns: {"table": table, "id": str, "op": "created" | "updated"} or {"error": str}
    """
    if table not in ALLOWED_TABLES:
        logger.warning(f"Attempt to upsert into forbidden table '{table}' by user {user.id}")
        return {"error": "forbidden_table", "table": table}

    # Validate against table-specific Pydantic schema
    validator = TABLE_VALIDATORS.get(table)
    if validator:
        try:
            validated_model = validator(**data)
            clean_data = validated_model.model_dump(exclude_none=True)
        except ValidationError as err:
            logger.info(f"Validation failed for table '{table}': {err.errors()}")
            return {"error": "validation_error", "table": table, "details": err.errors()}
    else:
        clean_data = dict(data)

    user_id = str(user.id)

    try:
        if table == "students":
            # Natural key: profile_id
            clean_data["profile_id"] = user_id
            clean_data.setdefault("source", "user_said")
            clean_data.setdefault("confidence", 1.0)

            existing = supabase_client.table("students").select("id").eq("profile_id", user_id).execute()
            if existing.data and len(existing.data) > 0:
                rec_id = str(existing.data[0]["id"])
                supabase_client.table("students").update(clean_data).eq("id", rec_id).execute()
                return {"table": table, "id": rec_id, "op": "updated"}
            else:
                rec_id = str(uuid.uuid4())
                clean_data["id"] = rec_id
                res = supabase_client.table("students").insert(clean_data).execute()
                if res.data and len(res.data) > 0:
                    rec_id = str(res.data[0].get("id", rec_id))
                return {"table": table, "id": rec_id, "op": "created"}

        elif table == "colleges":
            # Natural key: (lower(name), lower(city))
            clean_data["owner_id"] = user_id
            col_name = clean_data.get("name", "").strip()
            city = clean_data.get("city", "Mumbai").strip()
            clean_data["city"] = city

            existing = (
                supabase_client.table("colleges")
                .select("id, name, city")
                .ilike("name", col_name)
                .ilike("city", city)
                .execute()
            )
            if existing.data and len(existing.data) > 0:
                rec_id = str(existing.data[0]["id"])
                supabase_client.table("colleges").update(clean_data).eq("id", rec_id).execute()
                return {"table": table, "id": rec_id, "op": "updated"}
            else:
                rec_id = str(uuid.uuid4())
                clean_data["id"] = rec_id
                res = supabase_client.table("colleges").insert(clean_data).execute()
                if res.data and len(res.data) > 0:
                    rec_id = str(res.data[0].get("id", rec_id))
                return {"table": table, "id": rec_id, "op": "created"}

        elif table == "companies":
            # Natural key: lower(name)
            clean_data["owner_id"] = user_id
            comp_name = clean_data.get("name", "").strip()

            existing = supabase_client.table("companies").select("id, name").ilike("name", comp_name).execute()
            if existing.data and len(existing.data) > 0:
                rec_id = str(existing.data[0]["id"])
                supabase_client.table("companies").update(clean_data).eq("id", rec_id).execute()
                return {"table": table, "id": rec_id, "op": "updated"}
            else:
                rec_id = str(uuid.uuid4())
                clean_data["id"] = rec_id
                res = supabase_client.table("companies").insert(clean_data).execute()
                if res.data and len(res.data) > 0:
                    rec_id = str(res.data[0].get("id", rec_id))
                return {"table": table, "id": rec_id, "op": "created"}

        elif table == "contacts":
            from app.search.dedupe import upsert_contact

            source = clean_data.get("source", "user_said")
            source_url = clean_data.get("source_url")
            res = upsert_contact(supabase_client, clean_data, user, source=source, source_url=source_url)
            return {"table": table, "id": res["contact_id"], "op": res["op"]}

        elif table in ("education", "internships", "jobs", "skills"):
            # Ownership enforcement: find student_id where profile_id = user.id
            stu_res = supabase_client.table("students").select("id").eq("profile_id", user_id).execute()
            if not stu_res.data:
                logger.warning(f"No student record found for profile_id {user_id}")
                return {"error": "no_student_record", "table": table}

            student_id = str(stu_res.data[0]["id"])
            clean_data["profile_id"] = user_id
            clean_data["student_id"] = student_id
            clean_data.setdefault("source", "user_said")
            clean_data.setdefault("confidence", 1.0)

            op = "created"
            rec_id = None

            if table == "education":
                level = clean_data.get("level")
                existing = (
                    supabase_client.table("education")
                    .select("id")
                    .eq("student_id", student_id)
                    .eq("level", level)
                    .execute()
                )
                if existing.data and len(existing.data) > 0:
                    rec_id = str(existing.data[0]["id"])
                    supabase_client.table("education").update(clean_data).eq("id", rec_id).execute()
                    op = "updated"
                else:
                    rec_id = str(uuid.uuid4())
                    clean_data["id"] = rec_id
                    res = supabase_client.table("education").insert(clean_data).execute()
                    if res.data and len(res.data) > 0:
                        rec_id = str(res.data[0].get("id", rec_id))
                    op = "created"

            elif table == "internships":
                comp = clean_data.get("company") or ""
                role = clean_data.get("role") or ""
                all_existing = (
                    supabase_client.table("internships")
                    .select("id, company, role")
                    .eq("student_id", student_id)
                    .execute()
                )
                match = next(
                    (
                        r
                        for r in (all_existing.data or [])
                        if (r.get("company") or "").strip().lower() == comp.strip().lower()
                        and (r.get("role") or "").strip().lower() == role.strip().lower()
                    ),
                    None,
                )
                if match:
                    rec_id = str(match["id"])
                    supabase_client.table("internships").update(clean_data).eq("id", rec_id).execute()
                    op = "updated"
                else:
                    rec_id = str(uuid.uuid4())
                    clean_data["id"] = rec_id
                    res = supabase_client.table("internships").insert(clean_data).execute()
                    if res.data and len(res.data) > 0:
                        rec_id = str(res.data[0].get("id", rec_id))
                    op = "created"

            elif table == "jobs":
                comp = clean_data.get("company") or ""
                role = clean_data.get("role") or ""
                all_existing = (
                    supabase_client.table("jobs").select("id, company, role").eq("student_id", student_id).execute()
                )
                match = next(
                    (
                        r
                        for r in (all_existing.data or [])
                        if (r.get("company") or "").strip().lower() == comp.strip().lower()
                        and (r.get("role") or "").strip().lower() == role.strip().lower()
                    ),
                    None,
                )
                if match:
                    rec_id = str(match["id"])
                    supabase_client.table("jobs").update(clean_data).eq("id", rec_id).execute()
                    op = "updated"
                else:
                    rec_id = str(uuid.uuid4())
                    clean_data["id"] = rec_id
                    res = supabase_client.table("jobs").insert(clean_data).execute()
                    if res.data and len(res.data) > 0:
                        rec_id = str(res.data[0].get("id", rec_id))
                    op = "created"

            elif table == "skills":
                name = clean_data.get("name") or ""
                all_existing = supabase_client.table("skills").select("id, name").eq("student_id", student_id).execute()
                match = next(
                    (
                        r
                        for r in (all_existing.data or [])
                        if (r.get("name") or "").strip().lower() == name.strip().lower()
                    ),
                    None,
                )
                if match:
                    rec_id = str(match["id"])
                    supabase_client.table("skills").update(clean_data).eq("id", rec_id).execute()
                    op = "updated"
                else:
                    rec_id = str(uuid.uuid4())
                    clean_data["id"] = rec_id
                    res = supabase_client.table("skills").insert(clean_data).execute()
                    if res.data and len(res.data) > 0:
                        rec_id = str(res.data[0].get("id", rec_id))
                    op = "created"

            # Score-affecting tables: recompute score
            if table in ("education", "internships", "jobs"):
                trigger = "resume_parsed" if clean_data.get("source") == "resume" else "chat_upsert"
                try:
                    recompute_score(supabase_client, student_id, trigger=trigger)
                except Exception as exc:
                    logger.warning(f"Could not recompute score after upsert on {table}: {exc}")

            return {"table": table, "id": rec_id, "op": op}

    except Exception as exc:
        logger.error(f"Error handling upsert for table {table}: {exc}")
        return {"error": "database_error", "message": str(exc), "table": table}

    return {"error": "unhandled_table", "table": table}
