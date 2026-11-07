from typing import List

from supabase import Client

from app.logger import logger
from app.scoring.engine import (
    EducationItem,
    InternshipItem,
    JobItem,
    ScoreInput,
    ScoreResult,
    compute_score,
)


def load_student_for_scoring(supabase: Client, student_id: str) -> ScoreInput:
    """
    Loads student data from DB tables (education, internships, jobs, documents)
    and constructs a pure ScoreInput object.
    Documents and reference checks are loaded strictly from DB state.
    """
    # 1. Fetch education records
    edu_res = supabase.table("education").select("*").eq("student_id", student_id).execute()
    edu_items: List[EducationItem] = []
    for r in edu_res.data or []:
        val = r.get("score_value")
        score_val = float(val) if val is not None else None
        edu_items.append(
            EducationItem(
                level=r.get("level", "other"),
                score_value=score_val,
                score_scale=r.get("score_scale"),
                institution=r.get("institution"),
                degree=r.get("degree"),
                branch=r.get("branch"),
                source=r.get("source", "resume"),
            )
        )

    # 2. Fetch internships
    int_res = supabase.table("internships").select("*").eq("student_id", student_id).execute()
    int_items: List[InternshipItem] = []
    for r in int_res.data or []:
        int_items.append(
            InternshipItem(
                company=r.get("company"),
                role=r.get("role"),
                start_date=str(r["start_date"]) if r.get("start_date") else None,
                end_date=str(r["end_date"]) if r.get("end_date") else None,
                source=r.get("source", "resume"),
            )
        )

    # 3. Fetch jobs
    job_res = supabase.table("jobs").select("*").eq("student_id", student_id).execute()
    job_items: List[JobItem] = []
    for r in job_res.data or []:
        job_items.append(
            JobItem(
                company=r.get("company"),
                role=r.get("role"),
                start_date=str(r["start_date"]) if r.get("start_date") else None,
                end_date=str(r["end_date"]) if r.get("end_date") else None,
                source=r.get("source", "resume"),
            )
        )

    # 4. Check documents for pre_verified status (any pre-verified document)
    doc_res = supabase.table("documents").select("verification_status").eq("student_id", student_id).execute()
    documents_pre_verified = any(r.get("verification_status") == "pre_verified" for r in (doc_res.data or []))

    # 5. Reference check authorized flag (defaults False until Day 5)
    reference_check_authorized = False

    return ScoreInput(
        student_id=student_id,
        education=edu_items,
        internships=int_items,
        jobs=job_items,
        documents_pre_verified=documents_pre_verified,
        reference_check_authorized=reference_check_authorized,
    )


def recompute_score(
    supabase: Client,
    student_id: str,
    trigger: str = "manual",
) -> ScoreResult:
    """
    Recomputes the score for a student, writes a new score_events row, and returns ScoreResult.
    """
    score_input = load_student_for_scoring(supabase, student_id)
    score_result = compute_score(score_input)

    # Resolve profile_id
    profile_id = None
    stu_res = supabase.table("students").select("profile_id").eq("id", student_id).execute()
    if stu_res.data and len(stu_res.data) > 0:
        profile_id = stu_res.data[0].get("profile_id")

    event_data = {
        "student_id": student_id,
        "profile_id": profile_id,
        "score": score_result.score,
        "breakdown": [b.to_dict() for b in score_result.breakdown],
        "next_best_actions": score_result.next_best_actions,
        "documents_pre_verified": score_input.documents_pre_verified,
        "reference_check_authorized": score_input.reference_check_authorized,
        "trigger": trigger,
    }
    supabase.table("score_events").insert(event_data).execute()
    logger.info(f"Recomputed score for student {student_id}: {score_result.score} (trigger: {trigger})")

    return score_result
