from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.db.supabase import get_supabase_client
from app.dependencies import get_current_user
from app.models.api import AgentRunResponse
from app.models.db import UserProfile

router = APIRouter(prefix="/v1/agent-runs", tags=["Agent Runs"])


@router.get(
    "/{id}",
    response_model=AgentRunResponse,
    summary="Agent run + step log",
    description="Retrieves an agent run, its steps, and the derived summary.",
)
def get_agent_run(
    id: str,
    current_user: UserProfile = Depends(get_current_user),
    client: Client = Depends(get_supabase_client),
) -> AgentRunResponse:
    res = client.table("agent_runs").select("*").eq("id", id).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found",
        )

    run = res.data[0]
    # Check access: only creator can view their run
    if run.get("profile_id") and str(run["profile_id"]) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    steps = run.get("steps") or []
    summary = None
    for step in steps:
        if isinstance(step, dict) and step.get("type") == "search_summary":
            summary = step.get("summary")
            break

    if not summary:
        for step in reversed(steps):
            if isinstance(step, dict) and "summary" in step:
                summary = step.get("summary")
                break

    return AgentRunResponse(
        id=str(run["id"]),
        status=run.get("status", "completed"),
        steps=steps,
        summary=summary,
        created_at=run.get("created_at"),
    )
