from typing import Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from supabase import Client

from app.db.supabase import get_supabase_client
from app.dependencies import get_current_user
from app.models.api import OutreachDraftRequest, OutreachDraftResponse
from app.models.db import UserProfile
from app.search.outreach import create_outreach_draft

router = APIRouter(prefix="/v1/outreach", tags=["outreach"])


class LetterDraftRequest(BaseModel):
    kind: str = Field(default="invitation", description="'invitation' | 'interview' | 'offer'")
    contact_id: str
    channel: str = Field(default="email", description="'email' | 'linkedin'")
    sender_context: Optional[str] = None


class LetterDraftResponse(BaseModel):
    draft_id: str
    subject: Optional[str] = None
    body: str
    channel: str
    kind: str


@router.post("/draft", response_model=OutreachDraftResponse, status_code=status.HTTP_200_OK)
def draft_outreach_endpoint(
    body: OutreachDraftRequest,
    user: UserProfile = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """
    Drafts an outreach message tailored to a contact.
    Never sends anything. Stores private draft in outreach_drafts.
    """
    res = create_outreach_draft(
        client=supabase,
        user=user,
        contact_id=str(body.contact_id),
        channel=body.channel,
        sender_context=body.sender_context,
        kind="outreach",
    )
    return OutreachDraftResponse(
        draft_id=res["draft_id"],
        subject=res["subject"],
        body=res["body"],
        channel=res["channel"],
    )


@router.post("/letter", response_model=LetterDraftResponse, status_code=status.HTTP_200_OK)
def draft_letter_endpoint(
    body: LetterDraftRequest,
    user: UserProfile = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """
    Drafts an invitation, interview, or offer letter for a contact.
    Never sends anything.
    """
    res = create_outreach_draft(
        client=supabase,
        user=user,
        contact_id=str(body.contact_id),
        channel=body.channel,
        sender_context=body.sender_context,
        kind=body.kind,
    )
    return LetterDraftResponse(
        draft_id=res["draft_id"],
        subject=res["subject"],
        body=res["body"],
        channel=res["channel"],
        kind=res["kind"],
    )


@router.get("/drafts")
def list_user_drafts(
    user: UserProfile = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Lists drafts created by the current user."""
    res = supabase.table("outreach_drafts").select("*").eq("profile_id", str(user.id)).order("created_at", desc=True).execute()
    return res.data or []
