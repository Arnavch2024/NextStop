from datetime import date
import pytest
from app.scoring.engine import (
    EducationItem,
    InternshipItem,
    JobItem,
    ScoreInput,
    compute_score,
    months_between,
)


def test_base_score_empty():
    inp = ScoreInput()
    res = compute_score(inp)
    assert res.score == 20
    assert len(res.breakdown) == 1
    assert res.breakdown[0].reason == "Base score"
    assert res.breakdown[0].points == 20
    assert res.breakdown[0].source == "system"


def test_cap_at_100():
    # Construct input with massive points:
    # 20 base + 1 hs + 1 bachelors + 90 completed internships + 1 job + 10 years
    internships = [
        InternshipItem(company=f"Comp{i}", end_date="2024-01-01", source="resume")
        for i in range(90)
    ]
    inp = ScoreInput(
        today=date(2025, 1, 1),
        education=[
            EducationItem(level="twelfth", score_value=90.0, score_scale="percentage"),
            EducationItem(level="bachelors", score_value=9.0, score_scale="cgpa10"),
        ],
        internships=internships,
        jobs=[
            JobItem(company="Tech Corp", start_date="2010-01-01", end_date="2020-01-01")
        ],
        documents_pre_verified=True,
        reference_check_authorized=True,
    )
    res = compute_score(inp)
    assert res.score == 100


def test_hs_exactly_85_pct_no_points():
    inp = ScoreInput(
        education=[EducationItem(level="twelfth", score_value=85.0, score_scale="percentage")]
    )
    res = compute_score(inp)
    assert res.score == 20  # Base only


def test_hs_above_85_pct_one_point():
    inp = ScoreInput(
        education=[EducationItem(level="twelfth", score_value=85.01, score_scale="percentage", source="resume")]
    )
    res = compute_score(inp)
    assert res.score == 21
    hs_breakdown = [b for b in res.breakdown if "High school score" in b.reason]
    assert len(hs_breakdown) == 1
    assert hs_breakdown[0].points == 1


def test_hs_exactly_8_gpa_no_points():
    inp = ScoreInput(
        education=[EducationItem(level="twelfth", score_value=8.0, score_scale="gpa10")]
    )
    res = compute_score(inp)
    assert res.score == 20


def test_hs_above_8_gpa_one_point():
    inp = ScoreInput(
        education=[EducationItem(level="twelfth", score_value=8.01, score_scale="gpa10")]
    )
    res = compute_score(inp)
    assert res.score == 21


def test_cgpa4_exactly_3_2_no_points():
    # 3.2 * 2.5 = 8.0 -> not > 8.0
    inp = ScoreInput(
        education=[EducationItem(level="twelfth", score_value=3.2, score_scale="cgpa4")]
    )
    res = compute_score(inp)
    assert res.score == 20


def test_cgpa4_above_3_2_one_point():
    # 3.21 * 2.5 = 8.025 > 8.0 -> +1
    inp = ScoreInput(
        education=[EducationItem(level="twelfth", score_value=3.21, score_scale="cgpa4")]
    )
    res = compute_score(inp)
    assert res.score == 21


def test_missing_data_no_crash():
    inp = ScoreInput(
        education=[
            EducationItem(level="twelfth", score_value=None, score_scale=None),
            EducationItem(level="bachelors", score_value=None, score_scale="percentage"),
        ],
        internships=[
            InternshipItem(company=None, role=None, start_date=None, end_date=None)
        ],
        jobs=[
            JobItem(company=None, role=None, start_date=None, end_date=None)
        ],
    )
    res = compute_score(inp)
    # Base 20 + 1 for first-job (len(jobs) >= 1) = 21
    assert res.score == 21


def test_completed_vs_ongoing_internship():
    today = date(2025, 6, 1)
    inp = ScoreInput(
        today=today,
        internships=[
            InternshipItem(company="TCS", end_date="2025-05-31"),  # completed (< today)
            InternshipItem(company="Infosys", end_date=None),      # ongoing (no end_date)
            InternshipItem(company="Wipro", end_date="2025-07-01"), # future
        ]
    )
    res = compute_score(inp)
    # Base 20 + 1 for completed TCS internship = 21
    assert res.score == 21
    intern_reasons = [b.reason for b in res.breakdown if "internship" in b.reason.lower()]
    assert len(intern_reasons) == 1
    assert "TCS" in intern_reasons[0]


def test_first_job_one_point_only():
    inp = ScoreInput(
        jobs=[
            JobItem(company="Startup A", role="SDE 1"),
            JobItem(company="Startup B", role="SDE 2"),
        ]
    )
    res = compute_score(inp)
    # Base 20 + 1 first job = 21
    assert res.score == 21
    first_job_items = [b for b in res.breakdown if b.reason == "First full-time job"]
    assert len(first_job_items) == 1


def test_full_year_flooring_11mo():
    today = date(2025, 1, 1)
    inp = ScoreInput(
        today=today,
        jobs=[
            JobItem(company="Acme", start_date="2024-01-01", end_date="2024-12-01"), # 11 months
        ]
    )
    res = compute_score(inp)
    # Base 20 + 1 first job + 0 full years = 21
    assert res.score == 21
    year_items = [b for b in res.breakdown if "full year" in b.reason]
    assert len(year_items) == 0


def test_full_year_flooring_12mo():
    today = date(2025, 1, 1)
    inp = ScoreInput(
        today=today,
        jobs=[
            JobItem(company="Acme", start_date="2024-01-01", end_date="2025-01-01"), # 12 months
        ]
    )
    res = compute_score(inp)
    # Base 20 + 1 first job + 1 full year = 22
    assert res.score == 22
    year_items = [b for b in res.breakdown if "full year" in b.reason]
    assert len(year_items) == 1
    assert year_items[0].points == 1


def test_full_year_flooring_24mo():
    today = date(2025, 1, 1)
    inp = ScoreInput(
        today=today,
        jobs=[
            JobItem(company="Acme", start_date="2023-01-01", end_date="2025-01-01"), # 24 months
        ]
    )
    res = compute_score(inp)
    # Base 20 + 1 first job + 2 full years = 23
    assert res.score == 23
    year_items = [b for b in res.breakdown if "full year" in b.reason]
    assert len(year_items) == 1
    assert year_items[0].points == 2


def test_documents_pre_verified_plus2():
    inp = ScoreInput(documents_pre_verified=True)
    res = compute_score(inp)
    assert res.score == 22
    doc_items = [b for b in res.breakdown if b.reason == "Documents pre-verified"]
    assert len(doc_items) == 1
    assert doc_items[0].points == 2
    assert doc_items[0].source == "system"


def test_reference_check_authorized_plus2():
    inp = ScoreInput(reference_check_authorized=True)
    res = compute_score(inp)
    assert res.score == 22
    ref_items = [b for b in res.breakdown if b.reason == "Reference check authorized"]
    assert len(ref_items) == 1
    assert ref_items[0].points == 2
    assert ref_items[0].source == "system"


def test_breakdown_source_reflects_provenance():
    today = date(2025, 6, 1)
    inp = ScoreInput(
        today=today,
        education=[
            EducationItem(level="twelfth", score_value=90.0, score_scale="percentage", source="resume"),
            EducationItem(level="bachelors", score_value=88.0, score_scale="percentage", source="user_said"),
        ],
        internships=[
            InternshipItem(company="TCS", end_date="2025-01-01", source="resume"),
        ],
        jobs=[
            JobItem(company="Google", start_date="2024-01-01", end_date="2025-01-01", source="user_said"),
        ],
        documents_pre_verified=True,
    )
    res = compute_score(inp)
    source_map = {b.reason: b.source for b in res.breakdown}
    assert source_map["Base score"] == "system"
    assert source_map["High school score (>85% or >8.0 GPA)"] == "resume"
    assert source_map["Bachelors score (>85% or >8.0 CGPA)"] == "user_said"
    assert any("TCS" in k and source_map[k] == "resume" for k in source_map)
    assert source_map["First full-time job"] == "user_said"
    assert any("full year" in k and source_map[k] == "system" for k in source_map)
    assert source_map["Documents pre-verified"] == "system"
