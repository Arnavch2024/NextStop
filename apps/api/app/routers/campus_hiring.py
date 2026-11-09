import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from supabase import Client

from app.db.supabase import get_supabase_client
from app.dependencies import get_current_user
from app.logger import logger
from app.models.db import ProfileRole, UserProfile
from app.routers.student_records import ImportReport
from app.scoring.company_score import recompute_company_score

router = APIRouter(prefix="/v1/campus-hiring", tags=["campus-hiring"])


class CampusHiringRecord(BaseModel):
    id: str
    company_id: Optional[str] = None
    college_id: str
    college_name: Optional[str] = None
    cycle_year: int
    type: str  # internship | full_time
    students_interviewed: int = 0
    offers_made: int = 0
    created_at: Optional[str] = None


@router.post("", response_model=ImportReport)
async def import_campus_hiring(
    file: UploadFile = File(..., description="Consent notice: We'll read this file to build your campus hiring records."),
    user: UserProfile = Depends(get_current_user),
    client: Client = Depends(get_supabase_client),
):
    """
    Import campus hiring data from CSV. Company users only.
    Parsing is deterministic only. Recomputes company score after import.
    """
    if user.role != ProfileRole.COMPANY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only company users can import campus hiring data.",
        )

    company_id = user.company_id
    if not company_id:
        if user.is_demo:
            company_id = "comp-tcs-1"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Company profile is not linked to any company.",
            )

    content_bytes = await file.read()
    try:
        content_str = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        content_str = content_bytes.decode("latin-1")

    reader = csv.reader(io.StringIO(content_str))
    try:
        raw_headers = next(reader)
    except StopIteration:
        return ImportReport(imported=0, skipped=0, reasons=["Empty CSV file"])

    alias_map = {
        "college": "college_name",
        "college_name": "college_name",
        "campus": "college_name",
        "institution": "college_name",
        "year": "cycle_year",
        "cycle_year": "cycle_year",
        "type": "type",
        "hiring_type": "type",
        "interviewed": "students_interviewed",
        "students_interviewed": "students_interviewed",
        "offers": "offers_made",
        "offers_made": "offers_made",
    }

    col_mapping: Dict[int, str] = {}
    unmapped_columns = []
    for idx, raw_h in enumerate(raw_headers):
        clean_h = raw_h.strip().lower().replace(" ", "_")
        if clean_h in alias_map:
            col_mapping[idx] = alias_map[clean_h]
        else:
            if raw_h.strip():
                unmapped_columns.append(raw_h.strip())

    reasons: List[str] = [f"unmapped_column: {c}" for c in sorted(set(unmapped_columns))]

    # Load existing colleges to map name -> id
    colleges_res = client.table("colleges").select("id, name").execute()
    colleges_by_name = {c["name"].lower().strip(): c["id"] for c in (colleges_res.data or [])}

    imported_count = 0
    skipped_count = 0

    for row_idx, row in enumerate(reader, start=2):
        if not row or not any(cell.strip() for cell in row):
            continue

        row_data: Dict[str, Any] = {}
        for col_idx, cell_value in enumerate(row):
            if col_idx in col_mapping:
                field_name = col_mapping[col_idx]
                row_data[field_name] = cell_value.strip()

        col_name = row_data.get("college_name")
        if not col_name:
            skipped_count += 1
            reasons.append(f"Row {row_idx}: missing college name")
            continue

        # Resolve college_id
        col_id = colleges_by_name.get(col_name.lower().strip())
        if not col_id:
            # Create college if absent
            col_id = str(uuid.uuid4())
            try:
                client.table("colleges").insert({
                    "id": col_id,
                    "name": col_name,
                    "city": "Mumbai",
                }).execute()
                colleges_by_name[col_name.lower().strip()] = col_id
            except Exception:
                col_id = "col-mumbai-1"

        raw_year = row_data.get("cycle_year")
        try:
            cycle_year = int(raw_year) if raw_year else 2027
        except ValueError:
            skipped_count += 1
            reasons.append(f"Row {row_idx}: invalid cycle_year")
            continue

        h_type = row_data.get("type", "full_time").lower().strip().replace(" ", "_")
        if h_type not in ("internship", "full_time"):
            h_type = "full_time"

        try:
            interviewed = int(row_data.get("students_interviewed", 0) or 0)
        except ValueError:
            interviewed = 0

        try:
            offers = int(row_data.get("offers_made", 0) or 0)
        except ValueError:
            offers = 0

        row_payload = {
            "id": str(uuid.uuid4()),
            "company_id": company_id,
            "college_id": col_id,
            "cycle_year": cycle_year,
            "type": h_type,
            "students_interviewed": interviewed,
            "offers_made": offers,
            "profile_id": str(user.id),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Check existing row
        existing = (
            client.table("campus_hiring")
            .select("id")
            .eq("company_id", company_id)
            .eq("college_id", col_id)
            .eq("cycle_year", cycle_year)
            .eq("type", h_type)
            .execute()
        )
        if existing.data and len(existing.data) > 0:
            client.table("campus_hiring").update(row_payload).eq("id", existing.data[0]["id"]).execute()
        else:
            client.table("campus_hiring").insert(row_payload).execute()

        imported_count += 1

    # Recompute company score after import
    try:
        recompute_company_score(client, company_id=company_id)
    except Exception as e:
        logger.warning(f"Error recomputing company score after import: {e}")

    logger.info(f"Imported {imported_count} campus hiring rows for company {company_id}")
    return ImportReport(imported=imported_count, skipped=skipped_count, reasons=reasons)


@router.get("", response_model=List[CampusHiringRecord])
def list_campus_hiring(
    cycle_year: Optional[int] = Query(None, description="Cycle year filter"),
    type: Optional[str] = Query(None, description="Type: internship or full_time"),
    user: UserProfile = Depends(get_current_user),
    client: Client = Depends(get_supabase_client),
):
    """List campus hiring records for company (own rows)."""
    company_id = user.company_id or "comp-tcs-1"
    query = client.table("campus_hiring").select("*").eq("company_id", company_id)

    if cycle_year:
        query = query.eq("cycle_year", cycle_year)
    if type:
        query = query.eq("type", type)

    res = query.execute()
    rows = res.data or []

    # Enrich with college names
    colleges_res = client.table("colleges").select("id, name").execute()
    c_names = {str(c["id"]): c["name"] for c in (colleges_res.data or [])}

    records = []
    for r in rows:
        cid = str(r.get("college_id", ""))
        records.append(
            CampusHiringRecord(
                id=str(r["id"]),
                company_id=str(r.get("company_id", "")),
                college_id=cid,
                college_name=c_names.get(cid, "Partner College"),
                cycle_year=int(r.get("cycle_year", 2027)),
                type=str(r.get("type", "full_time")),
                students_interviewed=int(r.get("students_interviewed", 0)),
                offers_made=int(r.get("offers_made", 0)),
                created_at=r.get("created_at"),
            )
        )

    return records
