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
