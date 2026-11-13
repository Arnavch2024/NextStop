import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, Field
from supabase import Client

from app.db.supabase import get_supabase_client
from app.dependencies import get_current_user
from app.logger import logger
from app.models.db import ProfileRole, UserProfile

router = APIRouter(prefix="/v1", tags=["student-records"])


class ImportReport(BaseModel):
    imported: int
    skipped: int
    reasons: List[str] = Field(default_factory=list)


class StudentCard(BaseModel):
    id: str
    full_name: str
    branch: Optional[str] = None
    degree: Optional[str] = None
    score_value: Optional[float] = None
    score_scale: Optional[str] = None
    batch_year: int
    college_name: Optional[str] = None
    college_id: Optional[str] = None
    current_status: str
    student_score: Optional[int] = None
    unverified: bool = True


class StudentListResponse(BaseModel):
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    status_counts: Optional[Dict[str, int]] = None


class ClaimRequest(BaseModel):
    email: Optional[str] = None


class ClaimResponse(BaseModel):
    claimed: bool
    record: Optional[Dict[str, Any]] = None
    message: str


class ShareBatchRequest(BaseModel):
    shared: bool = True


class BatchShareResponse(BaseModel):
    college_id: str
    batch_year: int
    shared_with_recruiters: bool


class DiscoverabilityUpdate(BaseModel):
    opted_out: bool


def sanitize_csv_cell(val: Any) -> str:
    """Neutralize formula injection by prefixing =, +, -, @ with an apostrophe."""
    s = str(val) if val is not None else ""
    if s and s[0] in ("=", "+", "-", "@"):
        return "'" + s
    return s


@router.get("/student-records/template")
def get_student_records_template():
    """Returns sample CSV header row and example for deterministic student records import."""
    sample = (
        "full_name,email,batch_year,branch,degree,score_value,score_scale,current_status\n"
        "Riya Sharma,riya@college.edu,2027,Computer Engineering,BTech,8.9,cgpa10,in_college\n"
        "Aarav Patel,aarav@college.edu,2028,Information Technology,BTech,88.5,percentage,in_college\n"
    )
    return Response(
        content=sample,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="student_import_template.csv"'},
    )


@router.post("/student-records", response_model=ImportReport)
async def import_student_records(
    file: UploadFile = File(..., description="We'll read this file to build your student list."),
    user: UserProfile = Depends(get_current_user),
    client: Client = Depends(get_supabase_client),
):
    """
    Import student records from CSV. Placement officer only.
    Consent notice: We'll read this file to build your student list.
    Parsing is deterministic only (no LLM mapping). Cell contents are treated as untrusted data.
    """
    if user.role != ProfileRole.PLACEMENT_OFFICER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only placement officers can import student records.",
        )

    college_id = user.college_id
    if not college_id and user.email:
        from app.auth.college_resolution import resolve_college_from_email

        resolved = resolve_college_from_email(user.email, is_email_verified=True, client=client)
        if resolved:
            college_id = str(resolved["id"])
            user.college_id = college_id

    if not college_id:
        # Fallback to demo college if user is demo
        if user.is_demo:
            college_id = "col-mumbai-1"
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Placement officer college could not be resolved from verified email domain.",
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

    # Header normalization & alias mapping
    alias_map = {
        "name": "full_name",
        "full_name": "full_name",
        "fullname": "full_name",
        "email": "email",
        "college_email": "email",
        "batch": "batch_year",
        "batch_year": "batch_year",
        "year": "batch_year",
        "branch": "branch",
        "stream": "branch",
        "department": "branch",
        "degree": "degree",
        "program": "degree",
        "cgpa": "score_value",
        "score": "score_value",
        "percentage": "score_value",
        "score_value": "score_value",
        "score_scale": "score_scale",
        "scale": "score_scale",
        "status": "current_status",
        "current_status": "current_status",
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

    imported_count = 0
    skipped_count = 0

    valid_statuses = {"in_college", "internship", "full_time", "not_placed"}

    for row_idx, row in enumerate(reader, start=2):
        if not row or not any(cell.strip() for cell in row):
            continue

        row_data: Dict[str, Any] = {}
        for col_idx, cell_value in enumerate(row):
            if col_idx in col_mapping:
                field_name = col_mapping[col_idx]
                row_data[field_name] = cell_value.strip()

        # Validation: full_name required
        full_name = row_data.get("full_name")
        if not full_name:
            skipped_count += 1
            reasons.append(f"Row {row_idx}: missing name")
            continue

        # Validation: batch_year required (must be 2027 or 2028)
        raw_batch = row_data.get("batch_year")
        try:
            batch_year = int(raw_batch) if raw_batch else None
            if batch_year not in (2027, 2028):
                raise ValueError("Invalid year")
        except (ValueError, TypeError):
            skipped_count += 1
            reasons.append(f"Row {row_idx}: invalid batch_year")
            continue

        # Score parsing
        score_val = None
        raw_score = row_data.get("score_value")
        if raw_score:
            try:
                score_val = float(raw_score)
            except ValueError:
                pass

        score_scale = row_data.get("score_scale")
        if not score_scale and score_val is not None:
            score_scale = "cgpa10" if score_val <= 10.0 else "percentage"

        current_status = row_data.get("current_status", "in_college").lower().replace(" ", "_")
        if current_status not in valid_statuses:
            current_status = "in_college"

        record_id = str(uuid.uuid4())
        record = {
            "id": record_id,
            "college_id": college_id,
            "full_name": full_name,
            "email": row_data.get("email") or None,
            "batch_year": batch_year,
            "branch": row_data.get("branch") or None,
            "degree": row_data.get("degree") or None,
            "score_value": score_val,
            "score_scale": score_scale,
            "current_status": current_status,
            "is_demo_data": user.is_demo,
            "created_by_profile_id": str(user.id),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Check for existing record by (college_id, email)
        email = record.get("email")
        if email:
            existing = (
                client.table("student_records").select("id").eq("college_id", college_id).eq("email", email).execute()
            )
            if existing.data and len(existing.data) > 0:
                rec_id = existing.data[0]["id"]
                client.table("student_records").update(record).eq("id", rec_id).execute()
                imported_count += 1
                continue

        client.table("student_records").insert(record).execute()
        imported_count += 1

    logger.info(f"Imported {imported_count} student records, skipped {skipped_count} for college {college_id}")

    if imported_count > 0:
        try:
            from app.cache import invalidate_llm_cache

            invalidate_llm_cache(reason=f"student_records_imported_{imported_count}")
        except Exception as e_cache:
            logger.debug(f"Cache invalidation note: {e_cache}")

    return ImportReport(imported=imported_count, skipped=skipped_count, reasons=reasons)


@router.get("/student-records", response_model=StudentListResponse)
def list_student_records(
    q: Optional[str] = Query(None, description="Search query"),
    batch_year: Optional[int] = Query(None, description="Batch year (2027 or 2028)"),
    status: Optional[str] = Query(None, description="Student status"),
    branch: Optional[str] = Query(None, description="Branch/Department"),
    degree: Optional[str] = Query(None, description="Degree"),
    college_id: Optional[str] = Query(None, description="College UUID"),
    min_score: Optional[float] = Query(None, description="Minimum score value"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserProfile = Depends(get_current_user),
    client: Client = Depends(get_supabase_client),
):
    """
    Search student records:
    - Placement Officer: sees records for own college (full fields including email).
    - Company / Recruiter: sees visibility-filtered records (batch_shared AND NOT opted_out).
      Returns minimal fields only. Never returns email, phone, documents.
    - Demo users: see ONLY is_demo_data = true records. Non-demo users see ONLY is_demo_data = false.
    """
    # 1. Fetch raw student records based on role
    query = client.table("student_records").select("*")

    # Demo safety rule
    if user.is_demo:
        query = query.eq("is_demo_data", True)
    else:
        query = query.eq("is_demo_data", False)

    if user.role == ProfileRole.PLACEMENT_OFFICER:
        c_id = user.college_id
        if not c_id and user.email:
            from app.auth.college_resolution import resolve_college_from_email

            resolved = resolve_college_from_email(user.email, is_email_verified=True, client=client)
            if resolved:
                c_id = str(resolved["id"])
                user.college_id = c_id
        if not c_id and user.is_demo:
            c_id = "col-mumbai-1"
        if not c_id:
            return StudentListResponse(items=[], total=0, page=page, page_size=page_size, status_counts={})
        query = query.eq("college_id", c_id)
    elif user.role in (ProfileRole.COMPANY, ProfileRole.RECRUITER):
        # Additional college filter if provided
        if college_id:
            query = query.eq("college_id", college_id)
    elif user.role == ProfileRole.STUDENT:
        query = query.eq("claimed_by_profile_id", str(user.id))

    if batch_year:
        query = query.eq("batch_year", batch_year)
    if status:
        query = query.eq("current_status", status)
    if branch:
        query = query.ilike("branch", f"%{branch}%")
    if degree:
        query = query.ilike("degree", f"%{degree}%")

    res = query.execute()
    all_records = res.data or []

    # Free text search filter in memory
    if q and q.strip():
        term = q.strip().lower()
        all_records = [
            r
            for r in all_records
            if term in str(r.get("full_name", "")).lower()
            or term in str(r.get("branch", "")).lower()
            or term in str(r.get("email", "")).lower()
        ]

    if min_score is not None:
        all_records = [
            r for r in all_records if r.get("score_value") is not None and float(r["score_value"]) >= min_score
        ]

    # Fetch active reference authorizations (officers and companies see only a reference_check_authorized boolean)
    auth_profile_ids = set()
    auth_student_ids = set()
    try:
        auth_res = (
            client.table("reference_authorizations").select("profile_id, student_id").is_("revoked_at", None).execute()
        )
        for a in auth_res.data or []:
            if a.get("profile_id"):
                auth_profile_ids.add(str(a["profile_id"]))
            if a.get("student_id"):
                auth_student_ids.add(str(a["student_id"]))
    except Exception:
        pass

    # Apply company/recruiter visibility rule server-side:
    # visible iff batch_sharing.shared_with_recruiters == True AND NOT opted_out
    if user.role in (ProfileRole.COMPANY, ProfileRole.RECRUITER):
        shares_res = client.table("batch_sharing").select("college_id, batch_year, shared_with_recruiters").execute()
        shared_set = {
            (str(s["college_id"]), int(s["batch_year"]))
            for s in (shares_res.data or [])
            if s.get("shared_with_recruiters") is True
        }

        # Also get college names map
        colleges_res = client.table("colleges").select("id, name").execute()
        colleges_map = {str(c["id"]): c["name"] for c in (colleges_res.data or [])}

        visible_records = []
        for r in all_records:
            cid = str(r.get("college_id", ""))
            by = int(r.get("batch_year", 0))
            is_shared = (cid, by) in shared_set
            is_opted_out = bool(r.get("opted_out", False))

            if is_shared and not is_opted_out:
                # Strip private data! Minimal fields only:
                card = {
                    "id": str(r["id"]),
                    "full_name": r.get("full_name"),
                    "branch": r.get("branch"),
                    "degree": r.get("degree"),
                    "score_value": r.get("score_value"),
                    "score_scale": r.get("score_scale"),
                    "batch_year": r.get("batch_year"),
                    "college_id": cid,
                    "college_name": colleges_map.get(cid, "Mumbai Partner College"),
                    "current_status": r.get("current_status"),
                    "student_score": int(r.get("score_value") * 10)
                    if r.get("score_scale") == "cgpa10" and r.get("score_value")
                    else 75,
                    "reference_check_authorized": bool(
                        str(r.get("claimed_by_profile_id")) in auth_profile_ids or str(r.get("id")) in auth_student_ids
                    ),
                    "unverified": True,
                }
                visible_records.append(card)

        total = len(visible_records)
        start_idx = (page - 1) * page_size
        paged = visible_records[start_idx : start_idx + page_size]
        return StudentListResponse(items=paged, total=total, page=page, page_size=page_size)

    # For Placement Officer: calculate status counts and return paged records
    status_counts = {"in_college": 0, "internship": 0, "full_time": 0, "not_placed": 0}
    for r in all_records:
        r["reference_check_authorized"] = bool(
            str(r.get("claimed_by_profile_id")) in auth_profile_ids or str(r.get("id")) in auth_student_ids
        )
        st = r.get("current_status", "in_college")
        if st in status_counts:
            status_counts[st] += 1

    total = len(all_records)
    start_idx = (page - 1) * page_size
    paged = all_records[start_idx : start_idx + page_size]

    return StudentListResponse(
        items=paged,
        total=total,
        page=page,
        page_size=page_size,
        status_counts=status_counts,
    )


@router.get("/student-records/export")
def export_student_records(
    q: Optional[str] = Query(None),
    batch_year: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    branch: Optional[str] = Query(None),
    user: UserProfile = Depends(get_current_user),
    client: Client = Depends(get_supabase_client),
):
    """
    CSV export of student records for Placement Officers.
    Formula-injection neutralized: cells starting with =, +, -, @ are prefixed with '.
    """
    if user.role != ProfileRole.PLACEMENT_OFFICER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only placement officers can export student records.",
        )

    c_id = user.college_id
    if not c_id and user.email:
        from app.auth.college_resolution import resolve_college_from_email

        resolved = resolve_college_from_email(user.email, is_email_verified=True, client=client)
        if resolved:
            c_id = str(resolved["id"])
            user.college_id = c_id
    if not c_id:
        c_id = "col-mumbai-1"
    query = client.table("student_records").select("*").eq("college_id", c_id)
    if user.is_demo:
        query = query.eq("is_demo_data", True)
    else:
        query = query.eq("is_demo_data", False)

    if batch_year:
        query = query.eq("batch_year", batch_year)
    if status:
        query = query.eq("current_status", status)
    if branch:
        query = query.ilike("branch", f"%{branch}%")

    res = query.execute()
    records = res.data or []

    if q and q.strip():
        term = q.strip().lower()
        records = [
            r
            for r in records
            if term in str(r.get("full_name", "")).lower()
            or term in str(r.get("email", "")).lower()
            or term in str(r.get("branch", "")).lower()
        ]

    output = io.StringIO()
    fieldnames = [
        "full_name",
        "email",
        "batch_year",
        "branch",
        "degree",
        "score_value",
        "score_scale",
        "current_status",
    ]
    writer = csv.writer(output)
    writer.writerow(fieldnames)

    for r in records:
        row = [sanitize_csv_cell(r.get(f)) for f in fieldnames]
        writer.writerow(row)

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="students_export.csv"'},
    )


@router.post("/student-records/claim", response_model=ClaimResponse)
def claim_student_record(
    body: ClaimRequest,
    user: UserProfile = Depends(get_current_user),
    client: Client = Depends(get_supabase_client),
):
    """Allows a student to claim their student record by matching college email."""
    claim_email = body.email or user.email
    if not claim_email:
        raise HTTPException(status_code=400, detail="Email is required to claim a record.")

    clean_email = claim_email.strip().lower()

    # Determine student's college via email domain resolution or user profile
    user_college_id = user.college_id
    if not user_college_id:
        from app.auth.college_resolution import resolve_college_from_email

        resolved = resolve_college_from_email(clean_email, is_email_verified=True, client=client)
        if resolved and resolved.get("id"):
            user_college_id = str(resolved["id"])

    res = (
        client.table("student_records")
        .select("*")
        .ilike("email", clean_email)
        .is_("claimed_by_profile_id", None)
        .execute()
    )

    if not res.data or len(res.data) == 0:
        return ClaimResponse(
            claimed=False,
            record=None,
            message="No unclaimed student record found matching this email.",
        )

    matched = res.data[0]
    record_college_id = str(matched.get("college_id") or "")

    # Security check: student cannot claim record from another college
    if user_college_id and record_college_id and record_college_id != str(user_college_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot claim a student record from another college.",
        )

    client.table("student_records").update({"claimed_by_profile_id": str(user.id)}).eq("id", matched["id"]).execute()
    matched["claimed_by_profile_id"] = str(user.id)

    if not user.college_id and record_college_id:
        try:
            client.table("profiles").update({"college_id": record_college_id}).eq("id", str(user.id)).execute()
            user.college_id = record_college_id
        except Exception:
            pass

    return ClaimResponse(
        claimed=True,
        record=matched,
        message="Successfully claimed student profile.",
    )


@router.patch("/student-records/{id}/discoverability")
def update_discoverability(
    id: str,
    body: DiscoverabilityUpdate,
    user: UserProfile = Depends(get_current_user),
    client: Client = Depends(get_supabase_client),
):
    """Allows a student to update their opt-out status."""
    client.table("student_records").update({"opted_out": body.opted_out}).eq("id", id).execute()
    return {"id": id, "opted_out": body.opted_out}


@router.post("/colleges/me/batches/{year}/share", response_model=BatchShareResponse)
def toggle_batch_share(
    year: int,
    body: ShareBatchRequest,
    user: UserProfile = Depends(get_current_user),
    client: Client = Depends(get_supabase_client),
):
    """Placement officer toggles batch sharing with recruiters."""
    if user.role != ProfileRole.PLACEMENT_OFFICER:
        raise HTTPException(status_code=403, detail="Only placement officers can toggle batch sharing.")

    if year not in (2027, 2028):
        raise HTTPException(status_code=400, detail="Batch year must be 2027 or 2028.")

    c_id = user.college_id
    if not c_id and user.email:
        from app.auth.college_resolution import resolve_college_from_email

        resolved = resolve_college_from_email(user.email, is_email_verified=True, client=client)
        if resolved:
            c_id = str(resolved["id"])
            user.college_id = c_id
    if not c_id:
        c_id = "col-mumbai-1"

    existing = client.table("batch_sharing").select("id").eq("college_id", c_id).eq("batch_year", year).execute()

    if existing.data and len(existing.data) > 0:
        row_id = existing.data[0]["id"]
        client.table("batch_sharing").update(
            {
                "shared_with_recruiters": body.shared,
                "set_by_profile_id": str(user.id),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", row_id).execute()
    else:
        client.table("batch_sharing").insert(
            {
                "id": str(uuid.uuid4()),
                "college_id": c_id,
                "batch_year": year,
                "shared_with_recruiters": body.shared,
                "set_by_profile_id": str(user.id),
            }
        ).execute()

    return BatchShareResponse(
        college_id=c_id,
        batch_year=year,
        shared_with_recruiters=body.shared,
    )


@router.get("/colleges/me/batches/shares")
def get_batch_shares(
    user: UserProfile = Depends(get_current_user),
    client: Client = Depends(get_supabase_client),
):
    """Returns current batch sharing status for officer's college for 2027 and 2028."""
    c_id = user.college_id
    if not c_id and user.email:
        from app.auth.college_resolution import resolve_college_from_email

        resolved = resolve_college_from_email(user.email, is_email_verified=True, client=client)
        if resolved:
            c_id = str(resolved["id"])
            user.college_id = c_id
    if not c_id:
        c_id = "col-mumbai-1"
    res = client.table("batch_sharing").select("batch_year, shared_with_recruiters").eq("college_id", c_id).execute()
    shares_map = {int(r["batch_year"]): bool(r["shared_with_recruiters"]) for r in (res.data or [])}

    return [
        {"batch_year": 2027, "shared_with_recruiters": shares_map.get(2027, False)},
        {"batch_year": 2028, "shared_with_recruiters": shares_map.get(2028, False)},
    ]
