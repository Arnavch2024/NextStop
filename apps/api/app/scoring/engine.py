from dataclasses import dataclass, field
from datetime import date
from typing import Any, List, Optional


def parse_iso_date(val: Any) -> Optional[date]:
    if not val:
        return None
    if isinstance(val, date):
        return val
    try:
        s = str(val).strip()
        if "T" in s:
            s = s.split("T")[0]
        return date.fromisoformat(s)
    except Exception:
        return None


def months_between(start_iso: Optional[str], end_iso: Optional[str]) -> float:
    """Returns approximate months between two ISO date strings. Returns 0 if invalid."""
    if not start_iso or not end_iso:
        return 0.0
    try:
        s = parse_iso_date(start_iso)
        e = parse_iso_date(end_iso)
        if not s or not e or e < s:
            return 0.0
        return float((e.year - s.year) * 12 + (e.month - s.month))
    except Exception:
        return 0.0


THRESHOLDS = {"percentage": 85.0, "gpa10": 8.0, "cgpa10": 8.0}


def meets_threshold(value: Optional[float], scale: Optional[str]) -> bool:
    if value is None or scale is None:
        return False
    try:
        val = float(value)
    except (ValueError, TypeError):
        return False
    scale_str = str(scale).lower().strip()
    if scale_str == "cgpa4":
        return (val * 2.5) > 8.0  # strict >
    if scale_str in THRESHOLDS:
        return val > THRESHOLDS[scale_str]  # strict >
    return False


@dataclass
class EducationItem:
    level: str  # 'tenth', 'twelfth', 'bachelors', 'masters', 'other'
    score_value: Optional[float] = None
    score_scale: Optional[str] = None  # 'percentage', 'gpa10', 'cgpa10', 'cgpa4'
    institution: Optional[str] = None
    degree: Optional[str] = None
    branch: Optional[str] = None
    source: str = "resume"


@dataclass
class InternshipItem:
    company: Optional[str] = None
    role: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    source: str = "resume"


@dataclass
class JobItem:
    company: Optional[str] = None
    role: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None  # None = current
    source: str = "resume"


@dataclass
class ScoreInput:
    student_id: Optional[str] = None
    education: List[EducationItem] = field(default_factory=list)
    internships: List[InternshipItem] = field(default_factory=list)
    jobs: List[JobItem] = field(default_factory=list)
    documents_pre_verified: bool = False
    reference_check_authorized: bool = False
    today: Optional[date] = None


@dataclass
class BreakdownItem:
    reason: str
    points: int
    source: str  # 'system' | 'resume' | 'user_said'

    def to_dict(self):
        return {
            "reason": self.reason,
            "points": self.points,
            "source": self.source,
        }


@dataclass
class ScoreResult:
    score: int
    breakdown: List[BreakdownItem]
    next_best_actions: List[str]

    def to_dict(self):
        return {
            "score": self.score,
            "breakdown": [b.to_dict() for b in self.breakdown],
            "next_best_actions": self.next_best_actions,
        }


def compute_score(inp: ScoreInput) -> ScoreResult:
    """
    Deterministic pure scoring function adhering to docs/scoring.md.
    No LLM, DB, or network inside.
    """
    today_date = inp.today or date.today()
    breakdown: List[BreakdownItem] = []
    actions: List[str] = []

    # 1. Base score (always +20)
    breakdown.append(BreakdownItem(reason="Base score", points=20, source="system"))

    # 2. High school score (>85% or >8.0 GPA)
    # 12th preferred, fallback 10th
    twelfth_rec = next((e for e in inp.education if str(e.level).lower() in ("twelfth", "12th")), None)
    hs_rec = twelfth_rec
    if hs_rec is None or hs_rec.score_value is None:
        tenth_rec = next((e for e in inp.education if str(e.level).lower() in ("tenth", "10th")), None)
        if tenth_rec is not None:
            hs_rec = tenth_rec

    if hs_rec and meets_threshold(hs_rec.score_value, hs_rec.score_scale):
        breakdown.append(
            BreakdownItem(
                reason="High school score (>85% or >8.0 GPA)",
                points=1,
                source=hs_rec.source or "resume",
            )
        )
    else:
        actions.append("Add verified 12th or 10th marksheet (>85% or >8.0 GPA)")

    # 3. Bachelors score (>85% or >8.0 CGPA)
    bach_rec = next(
        (e for e in inp.education if str(e.level).lower() in ("bachelors", "undergraduate", "degree")),
        None,
    )
    if bach_rec and meets_threshold(bach_rec.score_value, bach_rec.score_scale):
        breakdown.append(
            BreakdownItem(
                reason="Bachelors score (>85% or >8.0 CGPA)",
                points=1,
                source=bach_rec.source or "resume",
            )
        )
    else:
        actions.append("Add latest semester marks or CGPA (>85% or >8.0 CGPA)")

    # 4. Per completed internship (+1 each, completed iff end_date <= today)
    has_internship = False
    for intern in inp.internships:
        end_d = parse_iso_date(intern.end_date)
        if end_d and end_d <= today_date:
            has_internship = True
            comp_name = f" at {intern.company}" if intern.company else ""
            breakdown.append(
                BreakdownItem(
                    reason=f"Completed internship{comp_name}",
                    points=1,
                    source=intern.source or "resume",
                )
            )
    if not has_internship:
        actions.append("Add completed internship experience")

    # 5. First full-time job (+1 once if len(jobs) >= 1)
    if inp.jobs and len(inp.jobs) >= 1:
        first_job = inp.jobs[0]
        breakdown.append(
            BreakdownItem(
                reason="First full-time job",
                points=1,
                source=first_job.source or "resume",
            )
        )

    # 6. Per full year in full-time work (floor(total_months / 12))
    total_job_months = 0.0
    for job in inp.jobs:
        if job.start_date:
            end_iso = job.end_date if job.end_date else today_date.isoformat()
            total_job_months += months_between(job.start_date, end_iso)

    full_years = int(total_job_months // 12)
    if full_years > 0:
        breakdown.append(
            BreakdownItem(
                reason=f"{full_years} full year(s) in full-time work",
                points=full_years,
                source="system",
            )
        )

    # 7. Documents pre-verified (+2)
    if inp.documents_pre_verified:
        breakdown.append(
            BreakdownItem(
                reason="Documents pre-verified",
                points=2,
                source="system",
            )
        )
    else:
        actions.append("Verify your academic documents for +2 points")

    # 8. Reference check authorized (+2)
    if inp.reference_check_authorized:
        breakdown.append(
            BreakdownItem(
                reason="Reference check authorized",
                points=2,
                source="system",
            )
        )
    else:
        actions.append("Authorize reference checks for +2 points")

    total_points = sum(item.points for item in breakdown)
    capped_score = min(100, total_points)

    return ScoreResult(
        score=capped_score,
        breakdown=breakdown,
        next_best_actions=actions[:3],
    )

