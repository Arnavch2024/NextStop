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


class AgentStep(BaseModel):
    type: AgentStepType
    tool: Optional[str] = None
    input: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None
    at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))


class RecordOp(str, Enum):
    CREATED = "created"
    UPDATED = "updated"


class RecordRef(BaseModel):
    table: str
    id: Optional[str] = None
    op: str = Field(description="'created' or 'updated'")


class ChatResponse(BaseModel):
    reply: str
    steps: List[AgentStep] = Field(default_factory=list)
    records_created: List[RecordRef] = Field(default_factory=list)


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
