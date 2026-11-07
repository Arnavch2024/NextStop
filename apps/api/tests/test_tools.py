from app.agent.tools import handle_upsert
from app.models.db import ProfileRole, UserProfile


def test_upsert_forbidden_table(mock_supabase):
    user = UserProfile(id="user-123", role=ProfileRole.STUDENT)
    res = handle_upsert(mock_supabase, user, "secret_admin_table", {"data": "foo"})
    assert "error" in res
    assert res["error"] == "forbidden_table"


def test_upsert_student_invalid_batch_year(mock_supabase):
    user = UserProfile(id="user-123", role=ProfileRole.STUDENT)
    # batch_year must be 2027 or 2028
    res = handle_upsert(
        mock_supabase,
        user,
        "students",
        {"full_name": "Riya Sharma", "batch_year": 2025},
    )
    assert res["error"] == "validation_error"


def test_upsert_student_valid_natural_key(mock_supabase):
    user = UserProfile(id="user-123", role=ProfileRole.STUDENT)
    # 1. First upsert -> created
    res1 = handle_upsert(
        mock_supabase,
        user,
        "students",
        {"full_name": "Riya Sharma", "batch_year": 2027, "degree": "BSc CS"},
    )
    assert res1["table"] == "students"
    assert res1["op"] == "created"
    assert res1["id"] is not None

    # Verify profile_id was set to user.id
    stored = mock_supabase.store["students"][0]
    assert stored["profile_id"] == "user-123"
    assert stored["full_name"] == "Riya Sharma"

    # 2. Second upsert -> updated by natural key (profile_id)
    res2 = handle_upsert(
        mock_supabase,
        user,
        "students",
        {"full_name": "Riya Sharma", "batch_year": 2027, "degree": "MSc CS"},
    )
    assert res2["table"] == "students"
    assert res2["op"] == "updated"
    assert res2["id"] == res1["id"]
    assert mock_supabase.store["students"][0]["degree"] == "MSc CS"


def test_upsert_college_natural_key(mock_supabase):
    user = UserProfile(id="user-123", role=ProfileRole.STUDENT)
    res1 = handle_upsert(
        mock_supabase,
        user,
        "colleges",
        {"name": "St. Xavier's College", "city": "Mumbai"},
    )
    assert res1["table"] == "colleges"
    assert res1["op"] == "created"

    # Second upsert case-insensitive match
    res2 = handle_upsert(
        mock_supabase,
        user,
        "colleges",
        {"name": "st. xavier's college", "city": "mumbai"},
    )
    assert res2["table"] == "colleges"
    assert res2["op"] == "updated"
    assert res2["id"] == res1["id"]


def test_upsert_company_and_contact(mock_supabase):
    user = UserProfile(id="recruiter-456", role=ProfileRole.RECRUITER)
    res_company = handle_upsert(
        mock_supabase,
        user,
        "companies",
        {"name": "Acme Tech", "industry": "Software"},
    )
    assert res_company["op"] == "created"
    comp_id = res_company["id"]

    res_contact = handle_upsert(
        mock_supabase,
        user,
        "contacts",
        {
            "company_id": comp_id,
            "full_name": "Karan Mehta",
            "email": "karan@acme.com",
            "title": "Lead Recruiter",
        },
    )
    assert res_contact["table"] == "contacts"
    assert res_contact["op"] == "created"

    # Update contact by natural key (company_id, email)
    res_contact_update = handle_upsert(
        mock_supabase,
        user,
        "contacts",
        {
            "company_id": comp_id,
            "full_name": "Karan Mehta",
            "email": "karan@acme.com",
            "phone": "+91 9876543210",
        },
    )
    assert res_contact_update["op"] == "updated"
    assert res_contact_update["id"] == res_contact["id"]
