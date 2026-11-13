import io
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

import docx
import pypdf
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from supabase import Client

from app.agent.resume_parser import parse_resume
from app.config import settings
from app.db.supabase import get_supabase_client, write_raw_event
from app.dependencies import get_current_user
from app.logger import logger
from app.models.api import (
    BreakdownItemModel,
    ReferenceAuthRequest,
    ReferenceAuthResponse,
    ResumeResponse,
    RevokeVerifyResponse,
    ScoreResponse,
    StudentProfileResponse,
    TimelineResponse,
    TimelineStation,
    VerifyMockRequest,
    VerifyMockResponse,
)
from app.models.db import UserProfile
from app.scoring.loader import recompute_score
from app.verification import get_verifier

router = APIRouter(prefix="/v1/students/me", tags=["students"])

ALLOWED_RESUME_MIMES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def extract_text_from_file(file_bytes: bytes, mime_type: str, filename: str) -> str:
    """Extracts text from PDF or DOCX bytes."""
    fname = filename.lower()
    if mime_type == "application/pdf" or fname.endswith(".pdf"):
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        pages_text = [p.extract_text() or "" for p in reader.pages]
        return "\n".join(pages_text).strip()
    elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or fname.endswith(
        ".docx"
    ):
        doc = docx.Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs]
        return "\n".join(paragraphs).strip()
    return ""


def get_or_create_student_id(supabase: Client, user: UserProfile) -> str:
    """Finds or auto-provisions a student record for this user."""
    res = supabase.table("students").select("id").eq("profile_id", user.id).execute()
    if res.data and len(res.data) > 0:
        return str(res.data[0]["id"])

    new_id = str(uuid.uuid4())
    supabase.table("students").insert(
        {
            "id": new_id,
            "profile_id": user.id,
            "full_name": user.display_name or "Student",
            "batch_year": 2027,
        }
    ).execute()
    return new_id


def compute_missing_fields(supabase: Client, student_id: str) -> List[str]:
    """Computes required fields still absent for a student."""
    missing = []
    stu_res = supabase.table("students").select("college_id, degree, batch_year").eq("id", student_id).execute()
    stu = stu_res.data[0] if (stu_res.data and len(stu_res.data) > 0) else {}

    if not stu.get("college_id"):
        missing.append("college")
    if not stu.get("degree"):
        missing.append("degree")
    if not stu.get("batch_year"):
        missing.append("batch_year")

    edu_res = supabase.table("education").select("level, score_value").eq("student_id", student_id).execute()
    edu_rows = edu_res.data or []
    has_hs = any(
        r.get("level") in ("tenth", "twelfth", "10th", "12th") and r.get("score_value") is not None for r in edu_rows
    )
    has_bachelors = any(
        r.get("level") in ("bachelors", "undergraduate") and r.get("score_value") is not None for r in edu_rows
    )
    if not has_hs:
        missing.append("high_school_score")
    if not has_bachelors:
        missing.append("bachelors_score")

    skill_res = supabase.table("skills").select("id").eq("student_id", student_id).execute()
    if not (skill_res.data and len(skill_res.data) > 0):
        missing.append("skills")

    return missing


def create_signed_url_helper(supabase: Client, bucket: str, path: str) -> str:
    """Safe helper to create signed storage URL."""
    try:
        storage_client = getattr(supabase, "storage", None)
        if storage_client and hasattr(storage_client, "from_"):
            res = storage_client.from_(bucket).create_signed_url(path, 3600)
            if isinstance(res, dict):
                return (
                    res.get("signedURL") or res.get("signed_url") or f"https://mock-storage.supabase.co/{bucket}/{path}"
                )
            return str(res)
    except Exception as exc:
        logger.info(f"Storage signed URL creation handled: {exc}")
    return f"https://mock-storage.supabase.co/{bucket}/{path}"


@router.post("/resume", response_model=ResumeResponse, status_code=status.HTTP_200_OK)
async def upload_resume(
    file: UploadFile = File(...),
    user: UserProfile = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """
    Upload and parse student resume.
    1. Validates MIME (415) and size <= 5MB (413).
    2. Extracts text from PDF or DOCX.
    3. Saves to Supabase Storage bucket 'resumes'.
    4. Inserts 'documents' row.
    5. Writes user_message raw_event.
    6. Runs resume-parsing agent.
    7. Recomputes score.
    8. Returns ResumeResponse.
    """
    content_type = file.content_type or ""
    filename = file.filename or "resume"
    if not user.role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not assigned. Please complete onboarding at /onboarding.",
        )
    ext = os.path.splitext(filename)[1].lower()

    # 1. Validate MIME
    is_valid_mime = content_type in ALLOWED_RESUME_MIMES or ext in (".pdf", ".docx")
    if not is_valid_mime:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{content_type}'. Only PDF and DOCX files are allowed.",
        )

    file_bytes = await file.read()

    # 2. Validate Size
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            if hasattr(status, "HTTP_413_REQUEST_ENTITY_TOO_LARGE")
            else 413,
            detail="File size exceeds the 5MB limit.",
        )

    # 3. Extract text
    resume_text = extract_text_from_file(file_bytes, content_type, filename)

    # 4. Resolve student_id
    student_id = get_or_create_student_id(supabase, user)

    # 5. Upload to Supabase Storage bucket 'resumes'
    file_ext = ext if ext else (".pdf" if "pdf" in content_type else ".docx")
    doc_uuid = str(uuid.uuid4())
    storage_path = f"{student_id}/{doc_uuid}{file_ext}"

    try:
        storage_client = getattr(supabase, "storage", None)
        if storage_client and hasattr(storage_client, "from_"):
            storage_client.from_("resumes").upload(storage_path, file_bytes, {"content-type": content_type})
    except Exception as exc:
        logger.warning(f"Storage upload note: {exc}")

    signed_url = create_signed_url_helper(supabase, "resumes", storage_path)

    # 6. Insert documents metadata row
    doc_id = str(uuid.uuid4())
    supabase.table("documents").insert(
        {
            "id": doc_id,
            "student_id": student_id,
            "profile_id": user.id,
            "kind": "resume",
            "storage_path": storage_path,
            "file_name": filename,
            "mime_type": content_type,
            "size_bytes": len(file_bytes),
            "verification_status": "pending",
        }
    ).execute()

    # 7. Write raw_event (capped text in payload)
    write_raw_event(
        user.id,
        source="user_message",
        payload={
            "message": resume_text[:500],
            "document_id": doc_id,
            "kind": "resume",
        },
        client=supabase,
    )

    # 8. Run resume-parsing agent
    records_created = parse_resume(
        resume_text=resume_text,
        user=user,
        student_id=student_id,
        supabase_client=supabase,
    )

    # 9. Recompute score
    score_res = recompute_score(supabase, student_id, trigger="resume_parsed")

    # 10. Compute missing fields
    missing_fields = compute_missing_fields(supabase, student_id)

    if records_created:
        try:
            from app.cache import invalidate_llm_cache

            invalidate_llm_cache(reason=f"resume_parsed_records_{len(records_created)}")
        except Exception as e_cache:
            logger.debug(f"Cache invalidation note: {e_cache}")

    return ResumeResponse(
        document_id=doc_id,
        signed_url=signed_url,
        records_created=records_created,
        missing_fields=missing_fields,
        score=ScoreResponse(
            score=score_res.score,
            breakdown=[
                BreakdownItemModel(reason=b.reason, points=b.points, source=b.source) for b in score_res.breakdown
            ],
            next_best_actions=score_res.next_best_actions,
        ),
    )


@router.get("/resume/{document_id}", status_code=status.HTTP_200_OK)
async def get_resume_signed_url(
    document_id: str,
    user: UserProfile = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Returns a fresh signed URL for a student's resume document."""
    res = supabase.table("documents").select("*").eq("id", document_id).eq("profile_id", user.id).execute()
    if not res.data or len(res.data) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied.",
        )

    doc = res.data[0]
    signed_url = create_signed_url_helper(supabase, "resumes", doc["storage_path"])
    return {"document_id": document_id, "signed_url": signed_url}


@router.get("/score", response_model=ScoreResponse, status_code=status.HTTP_200_OK)
async def get_student_score(
    user: UserProfile = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """
    Returns the student's score, breakdown, and next best actions from the latest score_events row.
    If no score_events row exists, computes one.
    """
    if not user.role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not assigned. Please complete onboarding at /onboarding.",
        )
    student_id = get_or_create_student_id(supabase, user)

    evt_res = (
        supabase.table("score_events")
        .select("*")
        .eq("student_id", student_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if evt_res.data and len(evt_res.data) > 0:
        evt = evt_res.data[0]
        breakdown_items = [
            BreakdownItemModel(
                reason=b.get("reason", ""),
                points=b.get("points", 0),
                source=b.get("source", "system"),
            )
            for b in evt.get("breakdown", [])
        ]
        return ScoreResponse(
            score=evt.get("score", 20),
            breakdown=breakdown_items,
            next_best_actions=evt.get("next_best_actions", []),
        )

    # Compute if no score_events row exists
    score_res = recompute_score(supabase, student_id, trigger="manual")
    return ScoreResponse(
        score=score_res.score,
        breakdown=[BreakdownItemModel(reason=b.reason, points=b.points, source=b.source) for b in score_res.breakdown],
        next_best_actions=score_res.next_best_actions,
    )


@router.get("/profile", response_model=StudentProfileResponse, status_code=status.HTTP_200_OK)
async def get_student_profile(
    user: UserProfile = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Returns student profile and child arrays (education, internships, jobs, skills, documents)."""
    if not user.role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not assigned. Please complete onboarding at /onboarding.",
        )
    stu_res = supabase.table("students").select("*").eq("profile_id", user.id).execute()
    student_rec = stu_res.data[0] if (stu_res.data and len(stu_res.data) > 0) else None

    if not student_rec:
        return StudentProfileResponse(
            student=None,
            education=[],
            internships=[],
            jobs=[],
            skills=[],
            documents=[],
        )

    student_id = str(student_rec["id"])
    edu = supabase.table("education").select("*").eq("student_id", student_id).execute().data or []
    internships = supabase.table("internships").select("*").eq("student_id", student_id).execute().data or []
    jobs = supabase.table("jobs").select("*").eq("student_id", student_id).execute().data or []
    skills = supabase.table("skills").select("*").eq("student_id", student_id).execute().data or []
    documents = supabase.table("documents").select("*").eq("student_id", student_id).execute().data or []

    return StudentProfileResponse(
        student=student_rec,
        education=edu,
        internships=internships,
        jobs=jobs,
        skills=skills,
        documents=documents,
    )


@router.post("/verify-mock", response_model=VerifyMockResponse, status_code=status.HTTP_200_OK)
def verify_mock(
    body: Optional[VerifyMockRequest] = None,
    user: UserProfile = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Trigger demo mock pre-verify — env-gated by DEMO_VERIFY_ENABLED (returns 404 if disabled).

    NEVER reads document file contents. Sets verified_flag and document_type from MIME only.
    """
    if not settings.DEMO_VERIFY_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo verification is disabled on this environment.",
        )
    if not user.role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not assigned. Please complete onboarding at /onboarding.",
        )

    student_id = get_or_create_student_id(supabase, user)

    # 1. Look up document for this student
    target_doc_id = body.document_id if body and body.document_id else None
    query = supabase.table("documents").select("*").eq("student_id", student_id)
    if target_doc_id:
        query = query.eq("id", target_doc_id)
    res = query.limit(1).execute()

    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No document found to verify. Please upload a document first.",
        )

    doc = res.data[0]
    doc_id = str(doc["id"])
    mime_type = doc.get("mime_type") or "application/pdf"

    # 2. Call verifier (NEVER reads file bytes or sends content to LLM/OCR)
    verifier = get_verifier()
    v_res = verifier.verify(doc_id, mime_type)

    doc_type = (body.document_type if body and body.document_type else None) or v_res.document_type
    raw_tail = (body.masked_id_tail if body and body.masked_id_tail else None) or v_res.masked_id_tail
    masked_tail = None
    if raw_tail:
        # Never store full Aadhaar/PAN; ensure masked format
        digits = re.sub(r"\D", "", raw_tail)
        if len(digits) >= 4:
            masked_tail = f"XXXX-XXXX-{digits[-4:]}"
        else:
            masked_tail = raw_tail[-4:]
    elif doc_type == "aadhaar":
        masked_tail = "XXXX-XXXX-1234"

    now_iso = datetime.now(timezone.utc).isoformat()
    supabase.table("documents").update(
        {
            "verified_flag": v_res.verified_flag,
            "verification_status": "pre_verified",
            "verified_at": now_iso,
            "verification_note": v_res.verification_note,
            "document_type": doc_type,
            "masked_id_tail": masked_tail,
        }
    ).eq("id", doc_id).execute()

    # 3. Recompute score with trigger 'pre_verify'
    score_res = recompute_score(supabase, student_id, trigger="pre_verify")

    return VerifyMockResponse(
        status="pre_verified",
        document_id=doc_id,
        verified_flag=True,
        verification_note=v_res.verification_note,
        score=ScoreResponse(
            score=score_res.score,
            breakdown=[
                BreakdownItemModel(reason=b.reason, points=b.points, source=b.source) for b in score_res.breakdown
            ],
            next_best_actions=score_res.next_best_actions,
        ),
    )


@router.delete("/verify-mock", response_model=RevokeVerifyResponse, status_code=status.HTTP_200_OK)
def revoke_verify(
    user: UserProfile = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Revoke document pre-verification.

    Clears verified_flag, masked_id_tail, and recomputes score.
    """
    if not user.role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not assigned. Please complete onboarding at /onboarding.",
        )

    student_id = get_or_create_student_id(supabase, user)

    # Clear flags on documents
    supabase.table("documents").update(
        {
            "verified_flag": False,
            "verification_status": "pending",
            "masked_id_tail": None,
            "verified_at": None,
            "verification_note": None,
        }
    ).eq("student_id", student_id).execute()

    # Recompute score with trigger 'pre_verify_revoked'
    score_res = recompute_score(supabase, student_id, trigger="pre_verify_revoked")

    return RevokeVerifyResponse(
        status="revoked",
        verified_flag=False,
        score=ScoreResponse(
            score=score_res.score,
            breakdown=[
                BreakdownItemModel(reason=b.reason, points=b.points, source=b.source) for b in score_res.breakdown
            ],
            next_best_actions=score_res.next_best_actions,
        ),
    )


@router.post("/reference-auth", response_model=ReferenceAuthResponse, status_code=status.HTTP_200_OK)
def authorize_reference_check(
    body: Optional[ReferenceAuthRequest] = None,
    user: UserProfile = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Authorize reference check. Must be called explicitly from the UI.

    Chat agent tools may only propose; text inside a resume or document can NEVER grant consent.
    Awards +2 points to student score and drafts a reference-request letter (never auto-sent).
    """
    if not user.role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not assigned. Please complete onboarding at /onboarding.",
        )

    student_id = get_or_create_student_id(supabase, user)
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    # 1. Insert or reactivate reference authorization
    auth_id = str(uuid.uuid4())
    internship_id = body.internship_id if body else None
    authorized_party = body.authorized_party if body else None
    authorized_role = body.authorized_role if body else None

    # Resolve internship company name if internship_id provided and authorized_party missing
    if internship_id and not authorized_party:
        try:
            int_res = supabase.table("internships").select("company").eq("id", internship_id).limit(1).execute()
            if int_res.data:
                authorized_party = int_res.data[0].get("company")
        except Exception:
            pass

    supabase.table("reference_authorizations").insert(
        {
            "id": auth_id,
            "student_id": student_id,
            "profile_id": user.id,
            "internship_id": internship_id,
            "authorized_party": authorized_party,
            "authorized_role": authorized_role,
            "authorized_at": now_iso,
            "revoked_at": None,
        }
    ).execute()

    # 2. Draft a reference-request letter to the internship company (never auto-sent)
    company_name = authorized_party or "Internship Employer"
    try:
        supabase.table("outreach_drafts").insert(
            {
                "id": str(uuid.uuid4()),
                "profile_id": user.id,
                "channel": "email",
                "subject": f"Reference Request — {user.display_name or 'Student'}",
                "body": (
                    f"Dear {company_name} Team,\n\n"
                    f"{user.display_name or 'The student'} has authorized a reference check regarding their internship experience. "
                    "Please confirm their tenure and performance.\n\n"
                    "Thank you."
                ),
                "kind": "outreach",
            }
        ).execute()
    except Exception as exc:
        logger.warning(f"Could not save draft reference letter: {exc}")

    # 3. Recompute score with trigger 'reference_auth' (+2 points)
    score_res = recompute_score(supabase, student_id, trigger="reference_auth")

    return ReferenceAuthResponse(
        id=auth_id,
        student_id=student_id,
        authorized_at=now_dt,
        revoked_at=None,
        reference_check_authorized=True,
        score=ScoreResponse(
            score=score_res.score,
            breakdown=[
                BreakdownItemModel(reason=b.reason, points=b.points, source=b.source) for b in score_res.breakdown
            ],
            next_best_actions=score_res.next_best_actions,
        ),
    )


@router.delete("/reference-auth", response_model=ReferenceAuthResponse, status_code=status.HTTP_200_OK)
def revoke_reference_check(
    user: UserProfile = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Revoke reference check authorization.

    Sets revoked_at and recomputes score immediately (drops +2 bonus).
    """
    if not user.role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not assigned. Please complete onboarding at /onboarding.",
        )

    student_id = get_or_create_student_id(supabase, user)
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    # Mark active authorizations revoked
    supabase.table("reference_authorizations").update({"revoked_at": now_iso}).eq("student_id", student_id).is_(
        "revoked_at", None
    ).execute()

    # Recompute score with trigger 'reference_revoked'
    score_res = recompute_score(supabase, student_id, trigger="reference_revoked")

    return ReferenceAuthResponse(
        id=str(uuid.uuid4()),
        student_id=student_id,
        authorized_at=now_dt,
        revoked_at=now_dt,
        reference_check_authorized=False,
        score=ScoreResponse(
            score=score_res.score,
            breakdown=[
                BreakdownItemModel(reason=b.reason, points=b.points, source=b.source) for b in score_res.breakdown
            ],
            next_best_actions=score_res.next_best_actions,
        ),
    )


def _parse_year(val: Optional[Any]) -> Optional[int]:
    if val is None:
        return None
    if isinstance(val, int):
        return val
    s = str(val).strip()
    if len(s) >= 4 and s[:4].isdigit():
        return int(s[:4])
    return None


def _format_source_badge(source: Optional[str]) -> str:
    s = (source or "resume").lower()
    if s == "user_said":
        return "User said"
    if s == "system":
        return "System"
    return "Resume"


@router.get("/timeline", response_model=TimelineResponse, status_code=status.HTTP_200_OK)
def get_student_timeline(
    user: UserProfile = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Railway-route timeline stations ordered by start_year ascending.

    Current station is highlighted according to the current-station rule:
    last station with a start and no end year; else the latest station with data;
    college with no end year is labeled 'in college'.
    """
    if not user.role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not assigned. Please complete onboarding at /onboarding.",
        )

    student_id = get_or_create_student_id(supabase, user)

    # 1. Fetch education, internships, jobs
    edu_res = supabase.table("education").select("*").eq("student_id", student_id).execute()
    int_res = supabase.table("internships").select("*").eq("student_id", student_id).execute()
    job_res = supabase.table("jobs").select("*").eq("student_id", student_id).execute()

    stations: List[TimelineStation] = []

    # Education stations
    for e in edu_res.data or []:
        lvl = str(e.get("level", "")).lower()
        inst = e.get("institution") or ""
        deg = e.get("degree") or ""
        br = e.get("branch") or ""
        sy = _parse_year(e.get("start_year"))
        ey = _parse_year(e.get("end_year"))
        source = _format_source_badge(e.get("source"))

        if "tenth" in lvl or "10" in lvl:
            kind = "school_10"
            title = inst or "Class X (10th Secondary)"
            subtitle = e.get("board_or_university") or "Secondary School"
        elif "twelfth" in lvl or "12" in lvl:
            kind = "school_12"
            title = inst or "Class XII (12th Higher Secondary)"
            subtitle = br or e.get("board_or_university") or "Higher Secondary"
        else:
            kind = "college"
            title = f"{deg} — {inst}" if deg and inst else (deg or inst or "College Degree")
            subtitle = br or "Higher Education"

        stations.append(
            TimelineStation(
                kind=kind,
                title=title,
                subtitle=subtitle,
                start_year=sy,
                end_year=ey,
                source_badge=source,
                is_current=False,
                is_future=False,
            )
        )

    # Internship stations
    for i in int_res.data or []:
        comp = i.get("company") or "Company"
        role = i.get("role") or "Intern"
        sy = _parse_year(i.get("start_date"))
        ey = _parse_year(i.get("end_date"))
        source = _format_source_badge(i.get("source"))
        stations.append(
            TimelineStation(
                kind="internship",
                title=f"{role} — {comp}",
                subtitle="Internship",
                start_year=sy,
                end_year=ey,
                source_badge=source,
                is_current=False,
                is_future=False,
            )
        )

    # Job stations
    for j in job_res.data or []:
        comp = j.get("company") or "Company"
        role = j.get("role") or "Full-Time Role"
        sy = _parse_year(j.get("start_date"))
        ey = _parse_year(j.get("end_date"))
        source = _format_source_badge(j.get("source"))
        stations.append(
            TimelineStation(
                kind="job",
                title=f"{role} — {comp}",
                subtitle="Full-Time Work",
                start_year=sy,
                end_year=ey,
                source_badge=source,
                is_current=False,
                is_future=False,
            )
        )

    # 2. Sort past/present stations by start_year ascending. Stations with no start_year placed after dated ones.
    dated = [s for s in stations if s.start_year is not None]
    undated = [s for s in stations if s.start_year is None]
    dated.sort(key=lambda s: s.start_year if s.start_year is not None else 0)
    past_present_stations = dated + undated

    # 3. Apply current-station rule:
    # "is_current = true on the last station where start_year is not null AND end_year is null (ongoing).
    # If no such station exists, is_current = true on the station with the highest start_year that has data.
    # A college station with a start_year and no end_year shows subtitle = 'in college' and is_current = true."
    ongoing_stations = [s for s in past_present_stations if s.start_year is not None and s.end_year is None]
    if ongoing_stations:
        current_station = ongoing_stations[-1]
    elif dated:
        current_station = dated[-1]
    elif past_present_stations:
        current_station = past_present_stations[-1]
    else:
        current_station = None

    for s in past_present_stations:
        if s is current_station:
            s.is_current = True
            if s.kind == "college" and s.start_year is not None and s.end_year is None:
                s.subtitle = "in college"

    # 4. Check future stations (pre_verify and reference_check)
    doc_res = supabase.table("documents").select("verified_flag").eq("student_id", student_id).execute()
    has_pre_verified = any(bool(r.get("verified_flag")) for r in (doc_res.data or []))

    ref_res = (
        supabase.table("reference_authorizations")
        .select("id")
        .eq("student_id", student_id)
        .is_("revoked_at", None)
        .limit(1)
        .execute()
    )
    has_ref_auth = bool(ref_res.data and len(ref_res.data) > 0)

    future_stations: List[TimelineStation] = [
        TimelineStation(
            kind="pre_verify_done" if has_pre_verified else "pre_verify_pending",
            title="Documents Pre-verified" if has_pre_verified else "Document Pre-verification",
            subtitle="Verified (Mocked)" if has_pre_verified else "+2 points available",
            is_current=False,
            is_future=True,
        ),
        TimelineStation(
            kind="reference_done" if has_ref_auth else "reference_pending",
            title="Reference Check Authorized" if has_ref_auth else "Reference Check Authorization",
            subtitle="Authorized ✓" if has_ref_auth else "+2 points available",
            is_current=False,
            is_future=True,
        ),
    ]

    all_stations = past_present_stations + future_stations
    return TimelineResponse(stations=all_stations)
