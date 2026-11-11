from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.agent.runner import run_agent_loop
from app.db.supabase import get_supabase_client
from app.dependencies import get_current_user
from app.logger import logger
from app.models.api import ChatRequest, ChatResponse
from app.models.db import UserProfile

router = APIRouter(prefix="/v1", tags=["Chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send a message to the agent",
    description="Conversational endpoint executing the role-aware agent loop with tool use.",
    responses={
        401: {"description": "Unauthorized - Missing or invalid Supabase JWT access token"},
    },
)
def chat_endpoint(
    request: ChatRequest,
    current_user: UserProfile = Depends(get_current_user),
    supabase_client: Client = Depends(get_supabase_client),
) -> ChatResponse:
    """
    1. Loads the user's role and details via the validated Supabase JWT dependency.
    2. Runs the multi-turn agent loop with Google Gemini (max 5 iterations).
    3. Persists user messages, tool calls, tool results, and agent replies to raw_events and agent_runs.
    4. Returns the final assistant reply, step traces, and created/updated records.
    """
    logger.info(f"Received chat message from user {current_user.id} (role={current_user.role})")
    if not current_user.role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not assigned. Please complete onboarding at /onboarding.",
        )
    try:
        response = run_agent_loop(
            user=current_user,
            message=request.message,
            supabase_client=supabase_client,
        )
        return response
    except Exception as exc:
        logger.error(f"Error processing chat request for user {current_user.id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request.",
        )
