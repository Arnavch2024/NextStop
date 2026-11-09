from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class ProfileRole(str, Enum):
    STUDENT = "student"
    PLACEMENT_OFFICER = "placement_officer"
    COMPANY = "company"
    RECRUITER = "recruiter"


class ContactRoleType(str, Enum):
    CAMPUS_RECRUITER = "campus_recruiter"
    PLACEMENT_OFFICER = "placement_officer"
    HR = "hr"
    OTHER = "other"


class AgentRunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EducationLevel(str, Enum):
    TENTH = "tenth"
    TWELFTH = "twelfth"
    BACHELORS = "bachelors"
    MASTERS = "masters"
    OTHER = "other"


class ScoreScale(str, Enum):
    PERCENTAGE = "percentage"
    GPA10 = "gpa10"
    CGPA10 = "cgpa10"
    CGPA4 = "cgpa4"


class DocumentKind(str, Enum):
    RESUME = "resume"
    ID_PROOF = "id_proof"
    CERTIFICATE = "certificate"
    OTHER = "other"


class VerificationStatus(str, Enum):
    PENDING = "pending"
    PRE_VERIFIED = "pre_verified"
    REJECTED = "rejected"


class StudentStatus(str, Enum):
    IN_COLLEGE = "in_college"
    INTERNSHIP = "internship"
    FULL_TIME = "full_time"
    NOT_PLACED = "not_placed"


class CampusHiringType(str, Enum):
    INTERNSHIP = "internship"
    FULL_TIME = "full_time"


class OutreachDraftKind(str, Enum):
    OUTREACH = "outreach"
    INVITATION = "invitation"
    INTERVIEW = "interview"
    OFFER = "offer"


class UserProfile(BaseModel):
    id: str
    role: Optional[ProfileRole] = None
    display_name: Optional[str] = None
    email: Optional[str] = None
    college_id: Optional[str] = None
    company_id: Optional[str] = None
    is_demo: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# --- Schemas for upsert_record tool validation ---


class StudentUpsertData(BaseModel):
    full_name: str = Field(..., min_length=1)
    batch_year: int = Field(..., description="Must be graduating batch 2027 or 2028")
    degree: Optional[str] = None
    college_id: Optional[str] = None
    source: Optional[str] = Field(default="user_said")
    confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("batch_year")
    @classmethod
    def validate_batch_year(cls, v: int) -> int:
        if v not in (2027, 2028):
            raise ValueError("batch_year must be either 2027 or 2028")
        return v


class CollegeUpsertData(BaseModel):
    name: str = Field(..., min_length=1)
    city: str = Field(default="Mumbai", min_length=1)
    source: Optional[str] = Field(default="user_said")
    confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)


class CompanyUpsertData(BaseModel):
    name: str = Field(..., min_length=1)
    industry: Optional[str] = None
    source: Optional[str] = Field(default="user_said")
    confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)


class ContactUpsertData(BaseModel):
    name: str = Field(..., min_length=1)
    company_id: Optional[str] = None
    college_id: Optional[str] = None
    title: Optional[str] = None
    role_type: Optional[str] = Field(default="other")
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    source: Optional[str] = Field(default="user_said")
    source_url: Optional[str] = None
    confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def handle_name_alias_and_drop_phone(cls, values: Any) -> Any:
        if isinstance(values, dict):
            # Map legacy full_name to name
            if "name" not in values and "full_name" in values:
                values["name"] = values["full_name"]
            # Never write phone to lake
            values.pop("phone", None)
        return values


class EducationUpsertData(BaseModel):
    level: str = Field(..., description="Level: tenth, twelfth, bachelors, masters, other")
    institution: Optional[str] = None
    degree: Optional[str] = None
    branch: Optional[str] = None
    board_or_university: Optional[str] = None
    score_value: Optional[float] = None
    score_scale: Optional[str] = None  # percentage, gpa10, cgpa10, cgpa4
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    source: Optional[str] = Field(default="user_said")
    confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        lvl = str(v).lower().strip()
        if lvl in ("10th", "tenth", "ssc", "x", "10"):
            return "tenth"
        if lvl in ("12th", "twelfth", "hsc", "xii", "12", "junior college"):
            return "twelfth"
        if lvl in (
            "bachelors",
            "undergraduate",
            "bachelor",
            "btech",
            "b.tech",
            "be",
            "b.e",
            "bsc",
            "b.sc",
            "bms",
            "b.m.s",
        ):
            return "bachelors"
        if lvl in ("masters", "postgraduate", "master", "mtech", "m.tech", "msc", "m.sc", "mba", "m.b.a"):
            return "masters"
        if lvl in ("tenth", "twelfth", "bachelors", "masters", "other"):
            return lvl
        return "other"


class InternshipUpsertData(BaseModel):
    company: Optional[str] = None
    company_id: Optional[str] = None
    role: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration_months: Optional[float] = None
    source: Optional[str] = Field(default="user_said")
    confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)


class JobUpsertData(BaseModel):
    company: Optional[str] = None
    company_id: Optional[str] = None
    role: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration_months: Optional[float] = None
    source: Optional[str] = Field(default="user_said")
    confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)


class SkillUpsertData(BaseModel):
    name: str = Field(..., min_length=1)
    proficiency: Optional[str] = None
    source: Optional[str] = Field(default="user_said")
    confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)


TABLE_VALIDATORS = {
    "students": StudentUpsertData,
    "colleges": CollegeUpsertData,
    "companies": CompanyUpsertData,
    "contacts": ContactUpsertData,
    "education": EducationUpsertData,
    "internships": InternshipUpsertData,
    "jobs": JobUpsertData,
    "skills": SkillUpsertData,
}

ALLOWED_TABLES = set(TABLE_VALIDATORS.keys())
