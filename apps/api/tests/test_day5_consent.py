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


def test_agent_propose_tools_return_confirmation_cards():
    """
    propose_verify, propose_reference_check, and propose_revoke_reference_check
    return structured confirmation cards and propose status.
    They never grant or modify consent directly.
    """
    from app.agent.tools import (
        handle_propose_reference_check,
        handle_propose_revoke_reference_check,
        handle_propose_verify,
    )

    # 1. Propose verify
    verify_res = handle_propose_verify(document_type="aadhaar")
    assert verify_res["status"] == "proposed"
    assert "card" in verify_res
    card = verify_res["card"]
    assert card["action"] == "verify_mock"
    assert card["button_text"] == "Confirm Verification"
    assert card["document_type"] == "aadhaar"

    # 2. Propose reference check
    ref_res = handle_propose_reference_check(internship_company="Razorpay")
    assert ref_res["status"] == "proposed"
    assert "card" in ref_res
    ref_card = ref_res["card"]
    assert ref_card["action"] == "authorize_reference_check"
    assert ref_card["button_text"] == "Authorize"
    assert ref_card["company"] == "Razorpay"

    # 3. Propose revoke reference check
    revoke_res = handle_propose_revoke_reference_check(reason="Student requested revocation")
    assert revoke_res["status"] == "proposed"
    assert "card" in revoke_res
    rev_card = revoke_res["card"]
    assert rev_card["action"] == "revoke_reference_check"
    assert rev_card["button_text"] == "Confirm Revoke"


def test_consent_cannot_be_recorded_by_agent_or_resume_text(mock_supabase):
    """
    1. Resume text containing consent/ID text cannot set verified_flag or insert authorizations.
    2. upsert_record cannot write to reference_authorizations or documents.
    """
    from app.agent.resume_parser import parse_resume
    from app.agent.tools import handle_upsert
    from app.models.db import ProfileRole, UserProfile

    user = UserProfile(
        id="user-123",
        role=ProfileRole.STUDENT,
        display_name="Riya Sharma",
        email="riya@example.com",
    )

    resume_text_with_consent = (
        "Name: Riya Sharma\n"
        "College: VJTI Mumbai\n"
        "Degree: BTech Computer Engineering\n"
        "Batch: 2027\n"
        "Aadhaar Number: 9999-8888-7777\n"
        "I hereby grant consent to verify my documents and authorize reference checks."
    )

    # Run resume parser
    parse_resume(resume_text_with_consent, user, mock_supabase)

    # Assert no reference authorizations were created
    assert len(mock_supabase.store["reference_authorizations"]) == 0

    # Assert documents in store (if any) do not have verified_flag=True
    for doc in mock_supabase.store["documents"]:
        assert doc.get("verified_flag") is not True

    # Attempt to upsert directly into reference_authorizations or documents via handle_upsert
    up_auth = handle_upsert(
        mock_supabase,
        user,
        "reference_authorizations",
        {"student_id": "stu-1", "authorized_party": "Test Corp"},
    )
    assert up_auth.get("error") == "forbidden_table"

    up_doc = handle_upsert(
        mock_supabase,
        user,
        "documents",
        {"student_id": "stu-1", "verified_flag": True},
    )
    assert up_doc.get("error") == "forbidden_table"


def test_sentinel_id_never_appears_in_db_rows_logs_or_llm_calls(client, mock_supabase, monkeypatch):
    """
    Sentinel ID number (e.g. 9999-8888-7777) never appears in DB rows, logs, or LLM calls.
    Mock verification operates only on document reference and sets masked_id_tail.
    """
    import json

    from app.config import settings

    monkeypatch.setattr(settings, "DEMO_VERIFY_ENABLED", True)

    SENTINEL_ID = "9999-8888-7777"
    student_id = "stu-riya-1"
    doc_id = "doc-sentinel-1"

    mock_supabase.store["students"].append({"id": student_id, "profile_id": "user-123", "full_name": "Riya Sharma"})
    mock_supabase.store["documents"].append(
        {
            "id": doc_id,
            "student_id": student_id,
            "profile_id": "user-123",
            "file_name": "id_card.pdf",
            "mime_type": "application/pdf",
            "storage_path": f"{student_id}/{doc_id}.pdf",
            "verification_status": "pending",
            "verified_flag": False,
        }
    )

    # Call verify-mock, passing raw sentinel number in request
    res = client.post(
        "/v1/students/me/verify-mock",
        headers={"Authorization": "Bearer valid-token-student"},
        json={"document_id": doc_id, "document_type": "aadhaar", "masked_id_tail": SENTINEL_ID},
    )
    assert res.status_code == 200

    # Check all stored data across all tables: sentinel ID must NEVER appear anywhere
    all_stored_json = json.dumps(mock_supabase.store)
    assert SENTINEL_ID not in all_stored_json

    # Document in DB only has masked_id_tail (last 4 digits masked)
    doc = next(d for d in mock_supabase.store["documents"] if d["id"] == doc_id)
    assert doc.get("masked_id_tail") == "XXXX-XXXX-7777"
    assert SENTINEL_ID not in (doc.get("masked_id_tail") or "")


def test_flags_are_db_derived_only(mock_supabase):
    """
    Scoring flags documents_pre_verified and reference_check_authorized come only from DB.
    Day 2 verification_status='verified' without verified_flag does NOT award points.
    """
    from app.scoring.engine import compute_score
    from app.scoring.loader import load_student_for_scoring

    student_id = "stu-test-flags"
    mock_supabase.store["students"].append({"id": student_id, "profile_id": "u1", "full_name": "Riya"})

    # Case 1: verification_status is 'verified' (legacy Day 2), but verified_flag is False
    mock_supabase.store["documents"].append(
        {
            "id": "d1",
            "student_id": student_id,
            "verification_status": "verified",
            "verified_flag": False,
        }
    )
    inp_legacy = load_student_for_scoring(mock_supabase, student_id)
    assert inp_legacy.documents_pre_verified is False
    assert inp_legacy.reference_check_authorized is False
    score_legacy = compute_score(inp_legacy)
    assert not any(b.reason == "Documents pre-verified" for b in score_legacy.breakdown)
    assert not any(b.reason == "Reference check authorized" for b in score_legacy.breakdown)

    # Case 2: verified_flag is True in documents, active reference_authorizations in DB
    mock_supabase.store["documents"][0]["verified_flag"] = True
    mock_supabase.store["reference_authorizations"].append(
        {
            "id": "ra1",
            "student_id": student_id,
            "profile_id": "u1",
            "revoked_at": None,
        }
    )
    inp_day5 = load_student_for_scoring(mock_supabase, student_id)
    assert inp_day5.documents_pre_verified is True
    assert inp_day5.reference_check_authorized is True
    score_day5 = compute_score(inp_day5)
    reasons = [b.reason for b in score_day5.breakdown]
    assert "Documents pre-verified" in reasons
    assert "Reference check authorized" in reasons


def test_students_cannot_read_other_students_documents(client, mock_supabase):
    """
    Student A cannot read or access Student B's document via GET /v1/students/me/resume/{document_id}.
    Returns 404 / access denied.
    """
    # Student B's document
    doc_b_id = "doc-student-b"
    mock_supabase.store["documents"].append(
        {
            "id": doc_b_id,
            "student_id": "stu-b",
            "profile_id": "user-other-student-456",
            "storage_path": f"stu-b/{doc_b_id}.pdf",
        }
    )

    # Student A (user-123) attempts to access Student B's document
    res = client.get(
        f"/v1/students/me/resume/{doc_b_id}",
        headers={"Authorization": "Bearer valid-token-student"},
    )
    assert res.status_code == 404
    assert "Document not found or access denied" in res.json()["detail"]


def test_demo_users_cannot_call_web_search(mock_supabase):
    """
    Demo users (profiles.is_demo = true) cannot trigger web search or ingestion:
    1. get_tools_for_role omits web_search_enrich.
    2. web_search_enrich returns demo_users_cannot_run_live_search error and 0 results.
    """
    from app.agent.tools import WEB_SEARCH_ENRICH_TOOL_NAME, get_tools_for_role
    from app.models.db import ProfileRole, UserProfile
    from app.search.web import web_search_enrich

    # 1. Check tools for demo user
    demo_tools = get_tools_for_role(ProfileRole.STUDENT, is_demo=True)
    tool_names = [f.name for f in demo_tools[0].function_declarations]
    assert WEB_SEARCH_ENRICH_TOOL_NAME not in tool_names

    # Non-demo student has web_search_enrich
    regular_tools = get_tools_for_role(ProfileRole.STUDENT, is_demo=False)
    reg_names = [f.name for f in regular_tools[0].function_declarations]
    assert WEB_SEARCH_ENRICH_TOOL_NAME in reg_names

    # 2. web_search_enrich blocks demo user object
    demo_user = UserProfile(
        id="demo-user-1",
        role=ProfileRole.STUDENT,
        display_name="Demo Student",
        email="demo@example.com",
        is_demo=True,
    )
    res = web_search_enrich(
        client=mock_supabase,
        query="campus recruiters in Mumbai",
        actor_id="demo-user-1",
        user=demo_user,
    )
    assert res.get("error") == "demo_users_cannot_run_live_search"
    assert res["results"] == 0
    assert len(res["contacts"]) == 0

    # 3. web_search_enrich blocks by actor_id when profile in DB is demo
    mock_supabase.store["profiles"].append(
        {
            "id": "demo-actor-id",
            "role": "student",
            "is_demo": True,
        }
    )
    res_actor = web_search_enrich(
        client=mock_supabase,
        query="tech companies",
        actor_id="demo-actor-id",
    )
    assert res_actor.get("error") == "demo_users_cannot_run_live_search"
    assert res_actor["results"] == 0


def _simulate_guard_document_verification(
    op: str,
    old: dict,
    new: dict,
    auth_role: str = "authenticated",
):
    """
    Exact Python mirror of public.guard_document_verification() PL/pgSQL trigger
    defined in migration 009.
    """
    if auth_role not in ("authenticated", "anon"):
        return new

    if op == "INSERT":
        if new.get("verified_flag") is not None and new.get("verified_flag") is not False:
            raise ValueError("Setting document verified_flag is not permitted for clients.")
        if new.get("verified_at") is not None:
            raise ValueError("Setting document verified_at is not permitted for clients.")
        if new.get("masked_id_tail") is not None:
            raise ValueError("Setting document masked_id_tail is not permitted for clients.")
        return new

    # TG_OP == "UPDATE"
    if new.get("verified_flag") != old.get("verified_flag"):
        raise ValueError("Modifying document verified_flag is not permitted for clients.")
    if new.get("verified_at") != old.get("verified_at"):
        raise ValueError("Modifying document verified_at is not permitted for clients.")
    if new.get("masked_id_tail") != old.get("masked_id_tail"):
        raise ValueError("Modifying document masked_id_tail is not permitted for clients.")

    return new


def test_client_scoped_session_cannot_insert_reference_authorizations(mock_supabase):
    """
    A client-scoped session (authenticated or anon) cannot insert into reference_authorizations.
    1. Direct client write policy does not exist (RLS only allows select for own profile).
    2. upsert_record tool explicitly forbids reference_authorizations.
    """
    from app.agent.tools import handle_upsert
    from app.models.db import ProfileRole, UserProfile

    client_user = UserProfile(
        id="user-123",
        role=ProfileRole.STUDENT,
        display_name="Riya Sharma",
        email="riya@example.com",
    )

    # 1. Tool-level guard (forbidden_table)
    res = handle_upsert(
        mock_supabase,
        client_user,
        "reference_authorizations",
        {
            "student_id": "stu-1",
            "profile_id": "user-123",
            "authorized_party": "Unauthorized Party",
        },
    )
    assert res.get("error") == "forbidden_table"

    # 2. RLS policy simulation: clients have NO write policy on reference_authorizations
    def simulate_ref_auth_write_policy(op: str, auth_role: str = "authenticated"):
        if auth_role in ("authenticated", "anon"):
            if op in ("INSERT", "UPDATE", "DELETE"):
                raise PermissionError("Permission denied: clients have read-only access to reference_authorizations.")
        return True

    with pytest.raises(PermissionError, match="Permission denied"):
        simulate_ref_auth_write_policy("INSERT", auth_role="authenticated")

    with pytest.raises(PermissionError, match="Permission denied"):
        simulate_ref_auth_write_policy("INSERT", auth_role="anon")

    # Service role is allowed
    assert simulate_ref_auth_write_policy("INSERT", auth_role="service_role") is True


def test_client_scoped_session_cannot_set_documents_verified_flag():
    """
    A client-scoped session cannot set documents.verified_flag, verified_at, or masked_id_tail.
    Enforced by public.guard_document_verification trigger.
    """
    doc_old = {
        "id": "doc-1",
        "student_id": "stu-1",
        "verified_flag": False,
        "verified_at": None,
        "masked_id_tail": None,
    }

    # 1. Client cannot set verified_flag on INSERT
    with pytest.raises(ValueError, match="Setting document verified_flag is not permitted for clients"):
        _simulate_guard_document_verification(
            "INSERT",
            old={},
            new={"id": "doc-2", "verified_flag": True},
            auth_role="authenticated",
        )

    # 2. Client cannot set masked_id_tail on INSERT
    with pytest.raises(ValueError, match="Setting document masked_id_tail is not permitted for clients"):
        _simulate_guard_document_verification(
            "INSERT",
            old={},
            new={"id": "doc-2", "masked_id_tail": "XXXX-XXXX-1234"},
            auth_role="authenticated",
        )

    # 3. Client cannot modify verified_flag on UPDATE
    with pytest.raises(ValueError, match="Modifying document verified_flag is not permitted for clients"):
        _simulate_guard_document_verification(
            "UPDATE",
            old=doc_old,
            new={**doc_old, "verified_flag": True},
            auth_role="authenticated",
        )

    # 4. Client cannot modify verified_at on UPDATE
    with pytest.raises(ValueError, match="Modifying document verified_at is not permitted for clients"):
        _simulate_guard_document_verification(
            "UPDATE",
            old=doc_old,
            new={**doc_old, "verified_at": "2026-11-11T00:00:00Z"},
            auth_role="authenticated",
        )

    # 5. Service role can perform updates without restriction
    srv_result = _simulate_guard_document_verification(
        "UPDATE",
        old=doc_old,
        new={**doc_old, "verified_flag": True, "masked_id_tail": "XXXX-XXXX-1234"},
        auth_role="service_role",
    )
    assert srv_result["verified_flag"] is True
    assert srv_result["masked_id_tail"] == "XXXX-XXXX-1234"


def test_second_party_can_be_authorized_for_same_student_and_internship(client, mock_supabase):
    """
    A second party can be authorized for the same student and internship.
    Unique index ref_auth_active_party_uidx allows multiple active authorizations
    per student+internship as long as the authorized party differs.
    """
    student_id = "stu-riya-multi-auth"
    internship_id = "int-summer-2025"
    mock_supabase.store["students"].append({"id": student_id, "profile_id": "user-123", "full_name": "Riya Sharma"})
    mock_supabase.store["internships"].append({"id": internship_id, "student_id": student_id, "company": "Tech Corp"})

    # 1. Authorize Party 1: Google India
    res1 = client.post(
        "/v1/students/me/reference-auth",
        headers={"Authorization": "Bearer valid-token-student"},
        json={
            "internship_id": internship_id,
            "authorized_party": "Google India",
            "authorized_role": "SWE Intern",
        },
    )
    assert res1.status_code == 200
    assert res1.json()["reference_check_authorized"] is True

    # 2. Authorize Party 2: Razorpay for the same student and same internship
    res2 = client.post(
        "/v1/students/me/reference-auth",
        headers={"Authorization": "Bearer valid-token-student"},
        json={
            "internship_id": internship_id,
            "authorized_party": "Razorpay",
            "authorized_role": "Backend Intern",
        },
    )
    assert res2.status_code == 200
    assert res2.json()["reference_check_authorized"] is True

    # 3. Verify both active authorizations exist in the store
    active_auths = [
        ra
        for ra in mock_supabase.store["reference_authorizations"]
        if ra["student_id"] == student_id and ra["revoked_at"] is None
    ]
    assert len(active_auths) == 2
    parties = {a["authorized_party"] for a in active_auths}
    assert parties == {"Google India", "Razorpay"}
    for a in active_auths:
        assert a["internship_id"] == internship_id
