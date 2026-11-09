from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from supabase import Client

from app.db.supabase import get_supabase_client
from app.dependencies import get_current_user
from app.models.db import UserProfile
from app.scoring.campus_score import recompute_campus_score
from app.scoring.company_score import recompute_company_score

router = APIRouter(prefix="/v1", tags=["Scoring"])


class CampusScoreResponse(BaseModel):
    campus_score: int
    campus_internship_score: int
    breakdown: List[Dict[str, Any]]
    flagged: List[str]
    next_best_actions: List[str]


class CompanyScoreResponse(BaseModel):
    score: int
    breakdown: List[Dict[str, Any]]
    next_best_actions: List[str]


@router.get(
    "/colleges/{id}/score",
    response_model=CampusScoreResponse,
    summary="Campus + internship score with breakdown + flagged",
    description="Computes campus and internship scores for a college based on campus hiring records.",
)
def get_college_score(
    id: str = Path(..., description="College UUID"),
    user: UserProfile = Depends(get_current_user),
    client: Client = Depends(get_supabase_client),
):
    result = recompute_campus_score(client, college_id=id)
    return result


@router.get(
    "/companies/{id}/score",
    response_model=CompanyScoreResponse,
    summary="Company score with breakdown",
    description="Computes company score based on campus hiring records.",
)
def get_company_score(
    id: str = Path(..., description="Company UUID"),
    user: UserProfile = Depends(get_current_user),
    client: Client = Depends(get_supabase_client),
):
    result = recompute_company_score(client, company_id=id)
    return result.to_dict()

