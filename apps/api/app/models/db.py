from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator


class ProfileRole(str, Enum):
    STUDENT = "student"
    PLACEMENT_OFFICER = "placement_officer"
    COMPANY = "company"
    RECRUITER = "recruiter"


class AgentRunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class UserProfile(BaseModel):
    id: str
    role: Optional[ProfileRole] = None
    display_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# --- Schemas for upsert_record tool validation ---

class StudentUpsertData(BaseModel):
    full_name: str = Field(..., min_length=1)
    batch_year: int = Field(..., description="Must be graduating batch 2027 or 2028")
    degree: Optional[str] = None
    college_id: Optional[str] = None

    @field_validator("batch_year")
    @classmethod
    def validate_batch_year(cls, v: int) -> int:
        if v not in (2027, 2028):
            raise ValueError("batch_year must be either 2027 or 2028")
        return v


class CollegeUpsertData(BaseModel):
    name: str = Field(..., min_length=1)
    city: str = Field(default="Mumbai", min_length=1)


class CompanyUpsertData(BaseModel):
    name: str = Field(..., min_length=1)
    industry: Optional[str] = None


class ContactUpsertData(BaseModel):
    full_name: str = Field(..., min_length=1)
    company_id: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


TABLE_VALIDATORS = {
    "students": StudentUpsertData,
    "colleges": CollegeUpsertData,
    "companies": CompanyUpsertData,
    "contacts": ContactUpsertData,
}

ALLOWED_TABLES = set(TABLE_VALIDATORS.keys())

