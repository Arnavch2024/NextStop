from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class DemoAccount(BaseModel):
    role: str
    display_name: str
    email: str
    description: str
    college_id: Optional[str] = None
    company_id: Optional[str] = None


class DemoLoginRequest(BaseModel):
    role: str


class DemoLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


DEMO_ACCOUNTS: List[DemoAccount] = [
    DemoAccount(
        role="placement_officer",
        display_name="Prof. Sunita Patil",
        email="placement.officer@stxaviers.edu",
        description="Training & Placement Officer at St. Xavier's College",
        college_id="col-mumbai-1",
    ),
    DemoAccount(
        role="company",
        display_name="Pooja Sharma",
        email="pooja.sharma@tcs.com",
        description="University Relations Lead at TCS",
        company_id="comp-tcs-1",
    ),
    DemoAccount(
        role="recruiter",
        display_name="Karan Mehta",
        email="karan.recruiter@apexsearch.com",
        description="Early Careers Talent Specialist",
    ),
    DemoAccount(
        role="student",
        display_name="Riya Sharma",
        email="riya.sharma@stxaviers.edu",
        description="Final Year BTech Computer Engineering, Batch 2027",
    ),
]


@router.get("/demo-accounts", response_model=List[DemoAccount])
def list_demo_accounts():
    """Returns available pre-seeded demo accounts. Open, no auth required."""
    return DEMO_ACCOUNTS


@router.post("/demo-login", response_model=DemoLoginResponse)
def demo_login(body: DemoLoginRequest):
    """
    Signs in as a pre-seeded demo account by role without a password.
    Env-gated by DEMO_LOGIN_ENABLED (defaults to false).
    Returns 403 Forbidden if disabled.
    """
    if not settings.DEMO_LOGIN_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo login is disabled on this environment.",
        )

    matched = next((a for a in DEMO_ACCOUNTS if a.role == body.role), None)
    if not matched:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown demo role: {body.role}. Valid roles: {[a.role for a in DEMO_ACCOUNTS]}",
        )

    token = f"demo-token-{matched.role}"
    user_info = {
        "id": f"demo-{matched.role}-id",
        "email": matched.email,
        "role": matched.role,
        "display_name": matched.display_name,
        "college_id": matched.college_id,
        "company_id": matched.company_id,
        "is_demo": True,
    }

    return DemoLoginResponse(access_token=token, user=user_info)
