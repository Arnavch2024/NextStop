from fastapi.testclient import TestClient

from app.agent.prompts import get_system_prompt_for_role
from app.auth.college_resolution import (
    fuzzy_match_college,
    get_candidate_domains,
    resolve_college_from_email,
)
from app.models.db import ProfileRole
from scripts.seed_college_domains import seed_college_domains


def test_candidate_domains():
    cands = get_candidate_domains("student.eng.vjti.ac.in")
    assert "student.eng.vjti.ac.in" in cands
    assert "eng.vjti.ac.in" in cands
    assert "vjti.ac.in" in cands
    # Bare suffixes must not be candidate domains
    assert "ac.in" not in cands
    assert "in" not in cands


def test_resolve_college_exact_domain_match(mock_supabase):
    col_id = "col-vjti-1"
    mock_supabase.store["colleges"].append(
        {
            "id": col_id,
            "name": "Veermata Jijabai Technological Institute (VJTI)",
            "city": "Mumbai",
        }
    )
    mock_supabase.store["college_domains"].append(
        {
            "id": "cd-1",
            "college_id": col_id,
            "domain": "vjti.ac.in",
            "kind": "staff",
            "source_url": "https://vjti.ac.in",
        }
    )

    res = resolve_college_from_email("placement@vjti.ac.in", is_email_verified=True, client=mock_supabase)
    assert res is not None
    assert res["id"] == col_id
    assert "VJTI" in res["name"]


def test_resolve_college_parent_domain_match(mock_supabase):
    col_id = "col-spit-1"
    mock_supabase.store["colleges"].append(
        {
            "id": col_id,
            "name": "Sardar Patel Institute of Technology (SPIT)",
            "city": "Mumbai",
        }
    )
    mock_supabase.store["college_domains"].append(
        {
            "id": "cd-2",
            "college_id": col_id,
            "domain": "spit.ac.in",
            "kind": "staff",
            "source_url": "https://spit.ac.in",
        }
    )

    # Subdomain of spit.ac.in
    res = resolve_college_from_email("aarav@student.spit.ac.in", is_email_verified=True, client=mock_supabase)
    assert res is not None
    assert res["id"] == col_id
    assert "SPIT" in res["name"]


def test_resolve_college_free_mail_never_matches(mock_supabase):
    col_id = "col-vjti-1"
    mock_supabase.store["colleges"].append(
        {
            "id": col_id,
            "name": "VJTI",
            "city": "Mumbai",
        }
    )
    mock_supabase.store["college_domains"].append(
        {
            "id": "cd-1",
            "college_id": col_id,
            "domain": "vjti.ac.in",
            "kind": "staff",
            "source_url": "https://vjti.ac.in",
        }
    )

    # Free-mail domains must never resolve to any college
    assert resolve_college_from_email("user@gmail.com", is_email_verified=True, client=mock_supabase) is None
    assert resolve_college_from_email("user@googlemail.com", is_email_verified=True, client=mock_supabase) is None
    assert resolve_college_from_email("user@yahoo.com", is_email_verified=True, client=mock_supabase) is None
    assert resolve_college_from_email("user@outlook.com", is_email_verified=True, client=mock_supabase) is None
    assert resolve_college_from_email("user@hotmail.com", is_email_verified=True, client=mock_supabase) is None


def test_resolve_college_unverified_email_never_resolves(mock_supabase):
    col_id = "col-vjti-1"
    mock_supabase.store["colleges"].append(
        {
            "id": col_id,
            "name": "VJTI",
            "city": "Mumbai",
        }
    )
    mock_supabase.store["college_domains"].append(
        {
            "id": "cd-1",
            "college_id": col_id,
            "domain": "vjti.ac.in",
            "kind": "staff",
            "source_url": "https://vjti.ac.in",
        }
    )

    # Unverified email must never resolve
    res = resolve_college_from_email("officer@vjti.ac.in", is_email_verified=False, client=mock_supabase)
    assert res is None


def test_unknown_domain_triggers_chat_question():
    # When user has no college linked
    prompt_without_college = get_system_prompt_for_role(ProfileRole.STUDENT, has_college=False)
    assert "Which college in Mumbai are you with?" in prompt_without_college
    assert "Just to confirm, are you at" in prompt_without_college

    # When user already has a college linked
    prompt_with_college = get_system_prompt_for_role(ProfileRole.STUDENT, has_college=True)
    assert "Which college in Mumbai are you with?" not in prompt_with_college


def test_fuzzy_match_college(mock_supabase):
    mock_supabase.store["colleges"].append(
        {
            "id": "col-vjti-1",
            "name": "Veermata Jijabai Technological Institute (VJTI)",
            "city": "Mumbai",
        }
    )
    mock_supabase.store["colleges"].append(
        {
            "id": "col-spit-1",
            "name": "Sardar Patel Institute of Technology (SPIT)",
            "city": "Mumbai",
        }
    )

    # Acronym match
    res = fuzzy_match_college("vjti", client=mock_supabase)
    assert res is not None
    assert res["id"] == "col-vjti-1"

    # Full name match
    res2 = fuzzy_match_college("Sardar Patel Institute", client=mock_supabase)
    assert res2 is not None
    assert res2["id"] == "col-spit-1"


def test_student_cannot_claim_record_from_another_college(client: TestClient, mock_supabase):
    # Set up VJTI and SPIT
    mock_supabase.store["colleges"].append(
        {
            "id": "col-vjti",
            "name": "VJTI",
            "city": "Mumbai",
        }
    )
    mock_supabase.store["colleges"].append(
        {
            "id": "col-spit",
            "name": "SPIT",
            "city": "Mumbai",
        }
    )
    mock_supabase.store["college_domains"].append(
        {
            "id": "cd-vjti",
            "college_id": "col-vjti",
            "domain": "vjti.ac.in",
            "kind": "student",
            "source_url": "https://vjti.ac.in",
        }
    )

    # Student record belongs to SPIT
    mock_supabase.store["student_records"].append(
        {
            "id": "rec-spit-1",
            "full_name": "Riya Sharma",
            "email": "riya@vjti.ac.in",
            "college_id": "col-spit",
            "batch_year": 2027,
            "claimed_by_profile_id": None,
            "is_demo_data": False,
        }
    )

    # Student with VJTI domain tries to claim SPIT record -> 403 Forbidden
    response = client.post(
        "/v1/student-records/claim",
        json={"email": "riya@vjti.ac.in"},
        headers={"Authorization": "Bearer valid-token-student"},
    )
    assert response.status_code == 403
    assert "Cannot claim a student record from another college" in response.json()["detail"]

    # Now make the record belong to VJTI -> claim succeeds
    mock_supabase.store["student_records"][0]["college_id"] = "col-vjti"
    success_resp = client.post(
        "/v1/student-records/claim",
        json={"email": "riya@vjti.ac.in"},
        headers={"Authorization": "Bearer valid-token-student"},
    )
    assert success_resp.status_code == 200
    assert success_resp.json()["claimed"] is True


def test_seed_college_domains_skips_missing_source(mock_supabase, tmp_path):
    csv_file = tmp_path / "test_domains.csv"
    csv_file.write_text(
        "college_name,domain,kind,source_url\n"
        "VJTI,vjti.ac.in,staff,https://vjti.ac.in\n"
        "FakeCollege,fake.edu,student,\n"  # missing source_url -> must be skipped
    )
    res = seed_college_domains(csv_path=csv_file, client=mock_supabase)
    assert res["imported"] == 1
    assert res["skipped"] == 1
    assert any("Missing source_url" in r for r in res["reasons"])
