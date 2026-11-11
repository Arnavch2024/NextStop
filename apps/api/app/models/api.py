from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok", json_schema_extra={"example": "ok"})
    version: str = Field(default="0.1.0", json_schema_extra={"example": "0.1.0"})
    time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="User text message to the agent",
        json_schema_extra={"example": "I'm Riya at St. Xavier's, batch 2027, BSc CS"},
    )


class AgentStepType(str, Enum):
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FINAL_REPLY = "final_reply"
    SEARCH_SUMMARY = "search_summary"


class AgentStep(BaseModel):
    type: AgentStepType
    tool: Optional[str] = None
    input: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))


class RecordOp(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    MERGED = "merged"


class RecordRef(BaseModel):
    table: str
    id: Optional[str] = None
    op: str = Field(description="'created', 'updated' or 'merged'")


# --- Day 3 Contact Models ---


class ContactSourceModel(BaseModel):
    source: str = Field(description="'seed' | 'resume' | 'user_said' | 'web'")
    source_url: Optional[str] = None
    domain: Optional[str] = None
    fetched_at: Optional[datetime] = None
    confidence: float = 1.0


class ContactCard(BaseModel):
    id: str
    name: str
    title: Optional[str] = None
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    college_id: Optional[str] = None
    college_name: Optional[str] = None
    role_type: str = "other"
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    location: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    source_published_date: Optional[str] = None
    stale: Optional[bool] = None
    confidence: Optional[float] = None
    unverified: Optional[bool] = None
    saved: bool = False
    is_sample: bool = False
    sources: List[ContactSourceModel] = Field(default_factory=list)
    first_seen_at: Optional[datetime] = None
    last_verified_at: Optional[datetime] = None


class ChatResponse(BaseModel):
    reply: str
    steps: List[AgentStep] = Field(default_factory=list)
    records_created: List[RecordRef] = Field(default_factory=list)
    contacts: List[ContactCard] = Field(default_factory=list)


# --- Day 2 Models for Student Slice ---


class BreakdownItemModel(BaseModel):
    reason: str
    points: int
    source: str = Field(description="'resume' | 'user_said' | 'system'")


class ScoreResponse(BaseModel):
    score: int
    breakdown: List[BreakdownItemModel]
    next_best_actions: List[str]


class ResumeResponse(BaseModel):
    document_id: str
    signed_url: str
    records_created: List[RecordRef]
    missing_fields: List[str]
    score: ScoreResponse


class StudentProfileResponse(BaseModel):
    student: Optional[Dict[str, Any]] = None
    education: List[Dict[str, Any]] = Field(default_factory=list)
    internships: List[Dict[str, Any]] = Field(default_factory=list)
    jobs: List[Dict[str, Any]] = Field(default_factory=list)
    skills: List[Dict[str, Any]] = Field(default_factory=list)
    documents: List[Dict[str, Any]] = Field(default_factory=list)


class TranscribeResponse(BaseModel):
    text: str


# --- Day 3 Models for Search Slice ---


class ContactListResponse(BaseModel):
    items: List[ContactCard] = Field(default_factory=list)
    page: int = 1
    page_size: int = 20
    total: int = 0


class SaveResponse(BaseModel):
    contact_id: str
    saved: bool


class SaveContactRequest(BaseModel):
    phone: Optional[str] = None


class OutreachDraftRequest(BaseModel):
    contact_id: str
    channel: str = Field(description="'email' | 'linkedin'")
    sender_context: Optional[str] = None


class OutreachDraftResponse(BaseModel):
    draft_id: str
    subject: Optional[str] = None
    body: str
    channel: str


class AgentRunResponse(BaseModel):
    id: str
    status: str
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Optional[str] = None
    created_at: Optional[datetime] = None


# --- Day 5 Models: Consent Flows & Railway-Route Timeline ---


class VerifyMockRequest(BaseModel):
    document_id: Optional[str] = None


class VerifyMockResponse(BaseModel):
    status: str = "pre_verified"
    document_id: str
    verified_flag: bool = True
    verification_note: str = "Demo verification (mocked)"
    score: ScoreResponse


class RevokeVerifyResponse(BaseModel):
    status: str = "revoked"
    verified_flag: bool = False
    score: ScoreResponse


class ReferenceAuthRequest(BaseModel):
    internship_id: Optional[str] = None
    authorized_party: Optional[str] = None
    authorized_role: Optional[str] = None


class ReferenceAuthResponse(BaseModel):
    id: str
    student_id: str
    authorized_at: datetime
    revoked_at: Optional[datetime] = None
    reference_check_authorized: bool = True
    score: ScoreResponse


class StationKind(str, Enum):
    SCHOOL_10 = "school_10"
    SCHOOL_12 = "school_12"
    COLLEGE = "college"
    INTERNSHIP = "internship"
    JOB = "job"
    PRE_VERIFY_PENDING = "pre_verify_pending"
    PRE_VERIFY_DONE = "pre_verify_done"
    REFERENCE_PENDING = "reference_pending"
    REFERENCE_DONE = "reference_done"


class TimelineStation(BaseModel):
    kind: str
    title: str
    subtitle: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    source_badge: Optional[str] = None
    is_current: bool = False
    is_future: bool = False


class TimelineResponse(BaseModel):
    stations: List[TimelineStation] = Field(default_factory=list)
