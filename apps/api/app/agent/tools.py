import uuid
from typing import Any, Dict, Optional
from google.genai import types
from pydantic import ValidationError
from supabase import Client

from app.logger import logger
from app.models.db import (
    ALLOWED_TABLES,
    TABLE_VALIDATORS,
    UserProfile,
)

UPSERT_RECORD_TOOL_NAME = "upsert_record"

UPSERT_RECORD_DECLARATION = types.FunctionDeclaration(
    name=UPSERT_RECORD_TOOL_NAME,
    description="Create or update a record in a structured table. Use for students, colleges, companies, contacts.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "table": types.Schema(
                type=types.Type.STRING,
                enum=list(ALLOWED_TABLES),
                description="The target table to upsert: 'students', 'colleges', 'companies', or 'contacts'",
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
            existing = (
                supabase_client.table("students")
                .select("id")
                .eq("profile_id", user_id)
                .execute()
            )
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

            existing = (
                supabase_client.table("companies")
                .select("id, name")
                .ilike("name", comp_name)
                .execute()
            )
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
            # Natural key: (company_id, lower(email))
            clean_data["owner_id"] = user_id
            company_id = clean_data.get("company_id")
            email = clean_data.get("email", "").strip().lower()

            query = supabase_client.table("contacts").select("id, company_id, email")
            if company_id:
                query = query.eq("company_id", company_id)
            if email:
                query = query.ilike("email", email)
            elif not company_id:
                query = query.ilike("full_name", clean_data.get("full_name", ""))

            existing = query.execute()
            if existing.data and len(existing.data) > 0:
                rec_id = str(existing.data[0]["id"])
                supabase_client.table("contacts").update(clean_data).eq("id", rec_id).execute()
                return {"table": table, "id": rec_id, "op": "updated"}
            else:
                rec_id = str(uuid.uuid4())
                clean_data["id"] = rec_id
                res = supabase_client.table("contacts").insert(clean_data).execute()
                if res.data and len(res.data) > 0:
                    rec_id = str(res.data[0].get("id", rec_id))
                return {"table": table, "id": rec_id, "op": "created"}

    except Exception as exc:
        logger.error(f"Error handling upsert for table {table}: {exc}")
        return {"error": "database_error", "message": str(exc), "table": table}

    return {"error": "unhandled_table", "table": table}

