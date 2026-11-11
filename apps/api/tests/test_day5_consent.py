import pytest

from app.db.schema_check import MissingMigrationError, check_database_schema


def test_schema_check_missing_migration_009(monkeypatch):
    """check_database_schema raises MissingMigrationError naming 009_day5_consent.sql when Day 5 schema is absent."""
    from unittest.mock import MagicMock

    monkeypatch.setattr("app.db.schema_check.should_skip_schema_check", lambda: False)
    mock_client = MagicMock()

    # Pass Day 3, 4, 6 checks
    def mock_table(table_name):
        builder = MagicMock()
        if table_name == "reference_authorizations":
            builder.select.return_value.limit.return_value.execute.side_effect = Exception("Table not found")
        else:
            builder.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        return builder

    mock_client.table.side_effect = mock_table

    with pytest.raises(MissingMigrationError) as exc_info:
        check_database_schema(client=mock_client, raise_on_error=True)

    assert "009_day5_consent.sql" in str(exc_info.value)


def test_verify_mock_404_when_flag_off(client, monkeypatch):
    """POST /v1/students/me/verify-mock returns 404 when DEMO_VERIFY_ENABLED is False."""
    from app.config import settings

    monkeypatch.setattr(settings, "DEMO_VERIFY_ENABLED", False)
    res = client.post(
        "/v1/students/me/verify-mock",
        headers={"Authorization": "Bearer valid-token-student"},
    )
    assert res.status_code == 404


def test_verify_mock_success_and_score_bonus(client, mock_supabase, monkeypatch):
    """
    POST /v1/students/me/verify-mock sets verified_flag=True,
    awards +2 score bonus with score_events row.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "DEMO_VERIFY_ENABLED", True)

    student_id = "stu-riya-1"
    mock_supabase.store["students"].append({"id": student_id, "profile_id": "user-123", "full_name": "Riya Sharma"})
    doc_id = "doc-test-1"
    mock_supabase.store["documents"].append(
        {
            "id": doc_id,
            "student_id": student_id,
            "profile_id": "user-123",
            "file_name": "sample_aadhaar.pdf",
            "mime_type": "application/pdf",
            "storage_path": f"{student_id}/{doc_id}.pdf",
            "verification_status": "pending",
            "verified_flag": False,
        }
    )

    res = client.post(
        "/v1/students/me/verify-mock",
        headers={"Authorization": "Bearer valid-token-student"},
        json={"document_id": doc_id},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["verified_flag"] is True
    assert data["verification_note"] == "Demo verification (mocked)"
    assert any(b["reason"] == "Documents pre-verified" and b["points"] == 2 for b in data["score"]["breakdown"])

    # Verify DB store
    doc_in_store = next(d for d in mock_supabase.store["documents"] if d["id"] == doc_id)
    assert doc_in_store["verified_flag"] is True
    assert doc_in_store["verification_status"] == "pre_verified"

    # Verify score_events row recorded
    score_events = mock_supabase.store["score_events"]
    assert len(score_events) > 0
    assert any(se.get("trigger") == "pre_verify" for se in score_events)


def test_revoke_verify_clears_flag_and_drops_score(client, mock_supabase, monkeypatch):
    """
    DELETE /v1/students/me/verify-mock clears verified_flag and score bonus drops by 2.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "DEMO_VERIFY_ENABLED", True)

    student_id = "stu-riya-1"
    doc_id = "doc-test-1"
    mock_supabase.store["students"].append({"id": student_id, "profile_id": "user-123", "full_name": "Riya Sharma"})
    doc_in_store = {
        "id": doc_id,
        "student_id": student_id,
        "profile_id": "user-123",
        "file_name": "sample_aadhaar.pdf",
        "mime_type": "application/pdf",
        "storage_path": f"{student_id}/{doc_id}.pdf",
        "verification_status": "pre_verified",
        "verified_flag": True,
        "masked_id_tail": "XXXX-XXXX-1234",
    }
    mock_supabase.store["documents"].append(doc_in_store)

    res = client.delete(
        "/v1/students/me/verify-mock",
        headers={"Authorization": "Bearer valid-token-student"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "revoked"
    assert data["verified_flag"] is False
    assert not any(b["reason"] == "Documents pre-verified" for b in data["score"]["breakdown"])

    # DB store verified_flag is False and masked_id_tail is None
    assert doc_in_store["verified_flag"] is False
    assert doc_in_store["masked_id_tail"] is None


def test_digilocker_verifier_raises_not_implemented():
    """DigiLockerVerifier raises NotImplementedError with partner registration guidance."""
    from app.verification import DigiLockerVerifier

    verifier = DigiLockerVerifier()
    with pytest.raises(NotImplementedError) as exc_info:
        verifier.verify("doc-1", "application/pdf")
    assert "DigiLockerVerifier requires partner registration" in str(exc_info.value)


def test_reference_auth_endpoint_and_draft_letter(client, mock_supabase):
    """
    POST /v1/students/me/reference-auth authorizes reference check,
    awards +2 points, writes a draft reference letter (never auto-sent).
    """
    student_id = "stu-riya-1"
    mock_supabase.store["students"].append({"id": student_id, "profile_id": "user-123", "full_name": "Riya Sharma"})

    res = client.post(
        "/v1/students/me/reference-auth",
        headers={"Authorization": "Bearer valid-token-student"},
        json={"authorized_party": "Google India", "authorized_role": "Software Engineering Intern"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["reference_check_authorized"] is True
    assert any(b["reason"] == "Reference check authorized" and b["points"] == 2 for b in data["score"]["breakdown"])

    # Verify authorization row in DB
    auth_rows = mock_supabase.store["reference_authorizations"]
    assert len(auth_rows) > 0
    active_auth = next(a for a in auth_rows if a["student_id"] == student_id)
    assert active_auth["revoked_at"] is None
    assert active_auth["authorized_party"] == "Google India"

    # Verify draft letter created (never sent)
    drafts = mock_supabase.store["outreach_drafts"]
    assert any("Reference Request" in d.get("subject", "") for d in drafts)


def test_reference_auth_revoke_drops_score(client, mock_supabase):
    """
    DELETE /v1/students/me/reference-auth marks authorization revoked,
    score drops 2 points immediately.
    """
    student_id = "stu-riya-1"
    mock_supabase.store["students"].append({"id": student_id, "profile_id": "user-123", "full_name": "Riya Sharma"})
    mock_supabase.store["reference_authorizations"].append(
        {
            "id": "ra-1",
            "student_id": student_id,
            "profile_id": "user-123",
            "authorized_at": "2026-11-10T00:00:00Z",
            "revoked_at": None,
        }
    )

    res = client.delete(
        "/v1/students/me/reference-auth",
        headers={"Authorization": "Bearer valid-token-student"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["reference_check_authorized"] is False
    assert not any(b["reason"] == "Reference check authorized" for b in data["score"]["breakdown"])

    # DB store revoked_at is now set
    ra = mock_supabase.store["reference_authorizations"][0]
    assert ra["revoked_at"] is not None


def test_officers_and_companies_see_only_reference_check_authorized_boolean(client, mock_supabase):
    """
    Officers and companies querying student cards see only the reference_check_authorized boolean,
    never documents, storage paths, or masked values.
    """
    student_id = "stu-riya-1"
    college_id = "col-mumbai-1"
    mock_supabase.store["students"].append({"id": student_id, "profile_id": "user-123", "full_name": "Riya Sharma"})
    mock_supabase.store["student_records"].append(
        {
            "id": "sr-1",
            "college_id": college_id,
            "full_name": "Riya Sharma",
            "email": "riya@example.com",
            "batch_year": 2027,
            "branch": "Computer Engineering",
            "degree": "BTech",
            "score_value": 9.0,
            "score_scale": "cgpa10",
            "current_status": "in_college",
            "claimed_by_profile_id": "user-123",
            "is_demo_data": False,
        }
    )
    # Batch sharing enabled
    mock_supabase.store["batch_sharing"].append(
        {"id": "bs-1", "college_id": college_id, "batch_year": 2027, "shared_with_recruiters": True}
    )
    # Active authorization exists
    mock_supabase.store["reference_authorizations"].append(
        {
            "id": "ra-1",
            "student_id": student_id,
            "profile_id": "user-123",
            "authorized_at": "2026-11-10T00:00:00Z",
            "revoked_at": None,
        }
    )

    # 1. Company reads student records
    comp_res = client.get(
        "/v1/student-records",
        headers={"Authorization": "Bearer valid-token-company"},
    )
    assert comp_res.status_code == 200
    items = comp_res.json()["items"]
    assert len(items) == 1
    card = items[0]
    assert card["reference_check_authorized"] is True
    # Verify no private document or masked values leaked
    assert "storage_path" not in card
    assert "masked_id_tail" not in card
    assert "documents" not in card


def test_student_timeline_ordering_and_current_station(client, mock_supabase):
    """
    GET /v1/students/me/timeline returns stations ordered by start_year ascending.
    Current station: last station with start_year and no end_year (college has subtitle='in college').
    """
    student_id = "stu-riya-1"
    mock_supabase.store["students"].append({"id": student_id, "profile_id": "user-123", "full_name": "Riya Sharma"})
    # 1. 10th (2018-2020)
    mock_supabase.store["education"].append(
        {
            "id": "edu-1",
            "student_id": student_id,
            "level": "tenth",
            "institution": "St. Mary High School",
            "start_year": 2018,
            "end_year": 2020,
            "source": "resume",
        }
    )
    # 2. 12th (2020-2022)
    mock_supabase.store["education"].append(
        {
            "id": "edu-2",
            "student_id": student_id,
            "level": "twelfth",
            "institution": "Mithibai Junior College",
            "start_year": 2020,
            "end_year": 2022,
            "source": "resume",
        }
    )
    # 3. College (2022 - Ongoing)
    mock_supabase.store["education"].append(
        {
            "id": "edu-3",
            "student_id": student_id,
            "level": "bachelors",
            "degree": "BTech Computer Engineering",
            "institution": "VJTI Mumbai",
            "start_year": 2022,
            "end_year": None,
            "source": "resume",
        }
    )
    # 4. Completed Internship (2023)
    mock_supabase.store["internships"].append(
        {
            "id": "int-1",
            "student_id": student_id,
            "company": "TCS",
            "role": "Software Engineering Intern",
            "start_date": "2023-06-01",
            "end_date": "2023-08-31",
            "source": "resume",
        }
    )

    res = client.get(
        "/v1/students/me/timeline",
        headers={"Authorization": "Bearer valid-token-student"},
    )
    assert res.status_code == 200
    stations = res.json()["stations"]
    assert len(stations) >= 4

    # Check station ordering
    past_stations = [s for s in stations if not s["is_future"]]
    assert len(past_stations) == 4
    assert past_stations[0]["kind"] == "school_10"
    assert past_stations[0]["start_year"] == 2018
    assert past_stations[1]["kind"] == "school_12"
    assert past_stations[1]["start_year"] == 2020
    assert past_stations[2]["kind"] == "college"
    assert past_stations[2]["start_year"] == 2022
    assert past_stations[3]["kind"] == "internship"
    assert past_stations[3]["start_year"] == 2023

    # College is the ongoing station (start_year=2022, end_year=None) -> is_current=True and subtitle='in college'
    college_st = past_stations[2]
    assert college_st["is_current"] is True
    assert college_st["subtitle"] == "in college"

    # Future stations at the end
    future_stations = [s for s in stations if s["is_future"]]
    assert len(future_stations) == 2
    assert future_stations[0]["kind"] in ("pre_verify_pending", "pre_verify_done")
    assert future_stations[1]["kind"] in ("reference_pending", "reference_done")


def test_student_timeline_fallback_highest_start_year(client, mock_supabase):
    """
    When no ongoing station exists (all have end_year), current station falls back
    to the station with the highest start_year that has data.
    """
    student_id = "stu-riya-1"
    mock_supabase.store["students"].append({"id": student_id, "profile_id": "user-123", "full_name": "Riya Sharma"})
    mock_supabase.store["education"].append(
        {
            "id": "edu-1",
            "student_id": student_id,
            "level": "bachelors",
            "institution": "VJTI",
            "start_year": 2020,
            "end_year": 2024,
            "source": "resume",
        }
    )
    mock_supabase.store["jobs"].append(
        {
            "id": "job-1",
            "student_id": student_id,
            "company": "Infosys",
            "role": "Systems Engineer",
            "start_date": "2024-07-01",
            "end_date": "2025-06-30",
            "source": "resume",
        }
    )

    res = client.get(
        "/v1/students/me/timeline",
        headers={"Authorization": "Bearer valid-token-student"},
    )
    assert res.status_code == 200
    stations = res.json()["stations"]
    past = [s for s in stations if not s["is_future"]]
    assert len(past) == 2
    # The job station (2024) has the highest start_year and becomes current station
    assert past[1]["kind"] == "job"
    assert past[1]["is_current"] is True
    assert past[0]["is_current"] is False
