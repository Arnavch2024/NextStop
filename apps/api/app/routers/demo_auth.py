import os
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from supabase import Client

from app.config import settings
from app.db.supabase import get_anon_client, get_supabase_client
from app.logger import logger

router = APIRouter(prefix="/v1/auth", tags=["auth"])

_demo_login_attempts: Dict[str, List[float]] = defaultdict(list)
RATE_LIMIT_WINDOW_SECONDS = 60.0
MAX_ATTEMPTS_PER_WINDOW = 5


def check_demo_login_rate_limit(client_ip: str) -> None:
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    attempts = [t for t in _demo_login_attempts[client_ip] if t > cutoff]
    if len(attempts) >= MAX_ATTEMPTS_PER_WINDOW:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded: too many demo login attempts. Please wait.",
        )
    attempts.append(now)
    _demo_login_attempts[client_ip] = attempts


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
    refresh_token: Optional[str] = None
    expires_at: Optional[int] = None
    token_type: str = "bearer"
    user: Dict[str, Any]


DEMO_ACCOUNTS: List[DemoAccount] = [
    DemoAccount(
        role="placement_officer",
        display_name="Prof. Sunita Patil",
        email="demo-officer@example.com",
        description="Training & Placement Officer at St. Xavier's College",
        college_id="col-mumbai-1",
    ),
    DemoAccount(
        role="company",
        display_name="Pooja Sharma",
        email="demo-company@example.com",
        description="University Relations Lead at TCS",
        company_id="comp-tcs-1",
    ),
    DemoAccount(
        role="recruiter",
        display_name="Karan Mehta",
        email="demo-recruiter@example.com",
        description="Early Careers Talent Specialist",
    ),
    DemoAccount(
        role="student",
        display_name="Riya Sharma",
        email="demo-student@example.com",
        description="Final Year BTech Computer Engineering, Batch 2027",
    ),
]


@router.get("/demo-accounts", response_model=List[DemoAccount])
def list_demo_accounts():
    """Returns available pre-seeded demo accounts. Open, no auth required."""
    return DEMO_ACCOUNTS


@router.post("/demo-login", response_model=DemoLoginResponse)
def demo_login(
    body: DemoLoginRequest,
    request: Request,
    anon_client: Client = Depends(get_anon_client),
    service_client: Client = Depends(get_supabase_client),
):
    """
    Signs in as a pre-seeded demo account by role.
    Env-gated by DEMO_LOGIN_ENABLED (returns 404 when disabled).
    Signs in through Supabase Auth using a short-lived anon client.
    """
    if not settings.DEMO_LOGIN_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo login is disabled on this environment.",
        )

    client_ip = request.client.host if request.client else "unknown"
    check_demo_login_rate_limit(client_ip)

    matched = next((a for a in DEMO_ACCOUNTS if a.role == body.role), None)
    if not matched:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown demo role: {body.role}. Valid roles: {[a.role for a in DEMO_ACCOUNTS]}",
        )

    password = (
        os.environ.get(f"DEMO_PASSWORD_{matched.role.upper()}")
        or settings.DEMO_USER_PASSWORD
        or os.environ.get("DEMO_USER_PASSWORD")
        or "mock-demo-password"
    )

    try:
        auth_res = anon_client.auth.sign_in_with_password(
            {
                "email": matched.email,
                "password": password,
            }
        )
    except Exception as exc:
        logger.error(f"Demo sign-in failed via Supabase Auth for {matched.email}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Demo user authentication failed. Please ensure demo users are seeded.",
        )

    session = getattr(auth_res, "session", None)
    user_obj = getattr(auth_res, "user", None)
    if not session or not getattr(session, "access_token", None):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to obtain Supabase Auth session for demo user.",
        )

    user_id = str(user_obj.id if user_obj else f"demo-{matched.role}-id")
    profile_data = {}
    try:
        p_res = service_client.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        if p_res.data:
            profile_data = p_res.data[0]
    except Exception:
        pass

    user_info = {
        "id": user_id,
        "email": matched.email,
        "role": matched.role,
        "display_name": profile_data.get("display_name") or matched.display_name,
        "college_id": profile_data.get("college_id") or matched.college_id,
        "company_id": profile_data.get("company_id") or matched.company_id,
        "is_demo": True,
    }

    return DemoLoginResponse(
        access_token=session.access_token,
        refresh_token=getattr(session, "refresh_token", None),
        expires_at=getattr(session, "expires_at", None),
        token_type="bearer",
        user=user_info,
    )
