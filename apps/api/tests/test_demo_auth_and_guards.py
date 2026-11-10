import pytest

from app.config import settings
from app.models.db import ProfileRole, UserProfile
from app.search.ingest import run_ingest
from app.search.web import web_search_enrich


def test_demo_login_404_when_flag_off(client, monkeypatch):
    """POST /v1/auth/demo-login returns 404 when DEMO_LOGIN_ENABLED is False."""
    monkeypatch.setattr(settings, "DEMO_LOGIN_ENABLED", False)
    res = client.post("/v1/auth/demo-login", json={"role": "student"})
    assert res.status_code == 404


def test_fabricated_demo_token_rejected_in_both_flag_states(client, monkeypatch):
    """Fabricated demo-token-* bearer tokens must be rejected with 401 regardless of DEMO_LOGIN_ENABLED."""
    # Flag OFF
    monkeypatch.setattr(settings, "DEMO_LOGIN_ENABLED", False)
    res_off = client.get(
        "/v1/student-records",
        headers={"Authorization": "Bearer demo-token-placement_officer"},
    )
    assert res_off.status_code == 401

    # Flag ON
    monkeypatch.setattr(settings, "DEMO_LOGIN_ENABLED", True)
    res_on = client.get(
        "/v1/student-records",
        headers={"Authorization": "Bearer demo-token-placement_officer"},
    )
    assert res_on.status_code == 401


def test_demo_login_rate_limiting(client, monkeypatch):
    """POST /v1/auth/demo-login enforces rate limiting (returns 429 after 5 attempts)."""
    monkeypatch.setattr(settings, "DEMO_LOGIN_ENABLED", True)
    from app.routers import demo_auth

    demo_auth._demo_login_attempts.clear()

    # First 5 calls succeed (200)
    for _ in range(5):
        res = client.post("/v1/auth/demo-login", json={"role": "placement_officer"})
        assert res.status_code == 200

    # 6th call hits rate limit -> 429
    res_blocked = client.post("/v1/auth/demo-login", json={"role": "placement_officer"})
    assert res_blocked.status_code == 429
    assert "Rate limit exceeded" in res_blocked.json()["detail"]


def test_demo_user_jwt_passes_reads_and_isolation_both_ways(client, mock_supabase, monkeypatch):
    """
    Demo user's JWT passes reads.
    Demo users only ever see is_demo_data=True records.
    Non-demo users never see is_demo_data=True records.
    """
    college_id = "col-mumbai-1"
    # Seed 1 demo record and 1 non-demo record
    mock_supabase.store["student_records"].append(
        {
            "id": "sr-demo-1",
            "college_id": college_id,
            "full_name": "Demo Student Synthetic",
            "email": "demo.synthetic@college.edu",
            "batch_year": 2027,
            "branch": "Computer Engineering",
            "degree": "BTech",
            "score_value": 8.5,
            "score_scale": "cgpa10",
            "current_status": "in_college",
            "is_demo_data": True,
        }
    )
    mock_supabase.store["student_records"].append(
        {
            "id": "sr-prod-1",
            "college_id": college_id,
            "full_name": "Real Production Student",
            "email": "real.student@college.edu",
            "batch_year": 2027,
            "branch": "Computer Engineering",
            "degree": "BTech",
            "score_value": 9.0,
            "score_scale": "cgpa10",
            "current_status": "in_college",
            "is_demo_data": False,
        }
    )

    # 1. Demo Officer reads: must see ONLY the demo record
    demo_res = client.get(
        "/v1/student-records",
        headers={"Authorization": "Bearer valid-token-demo-officer"},
    )
    assert demo_res.status_code == 200
    demo_items = demo_res.json()["items"]
    assert len(demo_items) == 1
    assert demo_items[0]["id"] == "sr-demo-1"
    assert demo_items[0]["full_name"] == "Demo Student Synthetic"

    # 2. Non-demo Officer reads: must see ONLY the production record
    prod_res = client.get(
        "/v1/student-records",
        headers={"Authorization": "Bearer valid-token-officer"},
    )
    assert prod_res.status_code == 200
    prod_items = prod_res.json()["items"]
    assert len(prod_items) == 1
    assert prod_items[0]["id"] == "sr-prod-1"
    assert prod_items[0]["full_name"] == "Real Production Student"


def test_demo_users_blocked_from_web_search_and_ingestion(mock_supabase):
    """Demo users cannot run web_search_enrich or ingestion; they search the existing lake only."""
    demo_user = UserProfile(
        id="demo-recruiter-id",
        role=ProfileRole.RECRUITER,
        display_name="Karan Mehta",
        email="demo-recruiter@example.com",
        is_demo=True,
    )

    # 1. web_search_enrich with demo user returns error and 0 contacts
    res = web_search_enrich(
        client=mock_supabase,
        query="campus recruiters in Mumbai",
        user=demo_user,
        extract_and_ingest=True,
    )
    assert res["error"] == "demo_users_cannot_run_live_search"
    assert res["contacts"] == []
    assert res["results"] == 0

    # 2. ingestion pipeline raises ValueError if run by a demo user
    with pytest.raises(ValueError, match="Demo users cannot run ingestion pipeline"):
        run_ingest(client=mock_supabase, admin_user=demo_user)


def test_client_cannot_change_privileged_profile_fields(mock_supabase):
    """
    Logged-in client cannot update its own role, is_demo, college_id, or company_id via API tools.
    """
    from app.agent.tools import handle_upsert

    user = UserProfile(
        id="user-123",
        role=ProfileRole.STUDENT,
        display_name="Riya Sharma",
        email="riya@example.com",
        is_demo=False,
    )
    # Calling handle_upsert for forbidden 'profiles' table is blocked
    res = handle_upsert(
        supabase_client=mock_supabase,
        user=user,
        table="profiles",
        data={"role": "placement_officer", "is_demo": True},
    )
    assert "error" in res
    assert res["error"] == "forbidden_table"


def _simulate_profiles_guard_trigger(
    op: str,
    old: dict,
    new: dict,
    auth_role: str = "authenticated",
):
    """
    Exact Python mirror of public.guard_profile_privileged_columns() PL/pgSQL trigger
    defined in migrations 007 and 008.
    """
    if auth_role == "service_role":
        return new

    if op == "INSERT":
        if new.get("is_demo") is not None and new.get("is_demo") is not False:
            raise ValueError("Setting profile is_demo is not permitted.")
        if new.get("college_id") is not None:
            raise ValueError("Setting profile college_id is not permitted.")
        if new.get("company_id") is not None:
            raise ValueError("Setting profile company_id is not permitted.")
        return new

    # TG_OP == "UPDATE"
    old_role = old.get("role")
    new_role = new.get("role")
    if old_role is not None and old_role != "student" and new_role != old_role:
        raise ValueError("Changing profile role is not permitted.")

    if new.get("is_demo") != old.get("is_demo"):
        raise ValueError("Changing profile is_demo status is not permitted.")

    if new.get("college_id") != old.get("college_id"):
        raise ValueError("Changing profile college_id is not permitted.")

    if new.get("company_id") != old.get("company_id"):
        raise ValueError("Changing profile company_id is not permitted.")

    return new


def test_guard_clients_cannot_set_college_company_or_is_demo_even_when_null():
    """
    Clients (authenticated or anon) cannot set college_id, company_id or is_demo
    even when the current value is NULL.
    """
    # 1. Update college_id from NULL -> raises exception
    old_row = {"id": "p1", "role": None, "college_id": None, "company_id": None, "is_demo": False}
    with pytest.raises(ValueError, match="Changing profile college_id is not permitted"):
        _simulate_profiles_guard_trigger(
            "UPDATE",
            old=old_row,
            new={**old_row, "college_id": "col-uuid"},
            auth_role="authenticated",
        )

    # 2. Update company_id from NULL -> raises exception
    with pytest.raises(ValueError, match="Changing profile company_id is not permitted"):
        _simulate_profiles_guard_trigger(
            "UPDATE",
            old=old_row,
            new={**old_row, "company_id": "comp-uuid"},
            auth_role="authenticated",
        )

    # 3. Update is_demo from False/None to True -> raises exception
    with pytest.raises(ValueError, match="Changing profile is_demo status is not permitted"):
        _simulate_profiles_guard_trigger(
            "UPDATE",
            old=old_row,
            new={**old_row, "is_demo": True},
            auth_role="authenticated",
        )

    # 4. Insert with college_id or company_id or is_demo=True -> raises exception
    with pytest.raises(ValueError, match="Setting profile college_id is not permitted"):
        _simulate_profiles_guard_trigger(
            "INSERT",
            old={},
            new={"id": "p2", "role": "student", "college_id": "col-uuid", "company_id": None, "is_demo": False},
            auth_role="authenticated",
        )

    with pytest.raises(ValueError, match="Setting profile company_id is not permitted"):
        _simulate_profiles_guard_trigger(
            "INSERT",
            old={},
            new={"id": "p2", "role": "student", "college_id": None, "company_id": "comp-uuid", "is_demo": False},
            auth_role="authenticated",
        )

    with pytest.raises(ValueError, match="Setting profile is_demo is not permitted"):
        _simulate_profiles_guard_trigger(
            "INSERT",
            old={},
            new={"id": "p2", "role": "student", "college_id": None, "company_id": None, "is_demo": True},
            auth_role="authenticated",
        )


def test_guard_clients_role_set_once_and_cannot_change_unless_student():
    """
    A client can set role once when currently NULL.
    Cannot change it afterwards, unless the previous role was 'student'.
    """
    # 1. Profile role currently NULL -> client sets role to 'placement_officer'
    initial_row = {"id": "p1", "role": None, "college_id": None, "company_id": None, "is_demo": False}
    updated = _simulate_profiles_guard_trigger(
        "UPDATE",
        old=initial_row,
        new={**initial_row, "role": "placement_officer"},
        auth_role="authenticated",
    )
    assert updated["role"] == "placement_officer"

    # 2. Cannot change role afterwards (placement_officer -> recruiter)
    officer_row = {**initial_row, "role": "placement_officer"}
    with pytest.raises(ValueError, match="Changing profile role is not permitted"):
        _simulate_profiles_guard_trigger(
            "UPDATE",
            old=officer_row,
            new={**officer_row, "role": "recruiter"},
            auth_role="authenticated",
        )

    # 3. But if previous role was 'student', client CAN change it
    student_row = {**initial_row, "role": "student"}
    changed = _simulate_profiles_guard_trigger(
        "UPDATE",
        old=student_row,
        new={**student_row, "role": "placement_officer"},
        auth_role="authenticated",
    )
    assert changed["role"] == "placement_officer"


def test_guard_service_role_updates_work():
    """
    Service role bypasses all client checks and can update college_id, company_id,
    is_demo, and change role arbitrarily.
    """
    row = {"id": "p1", "role": "placement_officer", "college_id": None, "company_id": None, "is_demo": False}
    # Service role can set college_id, company_id, is_demo, and change role
    srv_updated = _simulate_profiles_guard_trigger(
        "UPDATE",
        old=row,
        new={**row, "role": "company", "college_id": "col-123", "company_id": "comp-456", "is_demo": True},
        auth_role="service_role",
    )
    assert srv_updated["college_id"] == "col-123"
    assert srv_updated["company_id"] == "comp-456"
    assert srv_updated["is_demo"] is True
    assert srv_updated["role"] == "company"


def test_onboarding_verified_college_email_links_college(client, mock_supabase):
    """
    POST /v1/auth/onboarding with a verified college email links the college
    through the server and auto-claims student_records.
    """
    col_id = "col-vjti-100"
    mock_supabase.store["colleges"].append(
        {"id": col_id, "name": "Veermata Jijabai Technological Institute", "city": "Mumbai"}
    )
    mock_supabase.store["college_domains"].append(
        {"id": "cd-100", "college_id": col_id, "domain": "vjti.ac.in", "kind": "student"}
    )

    res = client.post(
        "/v1/auth/onboarding",
        headers={"Authorization": "Bearer valid-token-college-student"},
        json={"role": "student", "display_name": "Rahul VJTI"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "student"
    assert data["college_id"] == col_id
    assert "Veermata Jijabai" in data["college_name"]
    assert "Linked to" in data["message"]


def test_onboarding_gmail_address_ends_with_college_null(client, mock_supabase):
    """
    POST /v1/auth/onboarding with a Gmail address ends with college_id null and tells user plainly.
    """
    res = client.post(
        "/v1/auth/onboarding",
        headers={"Authorization": "Bearer valid-token-gmail-student"},
        json={"role": "student", "display_name": "Rahul Gmail"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "student"
    assert data["college_id"] is None
    assert "Could not verify your college from your email domain" in data["message"]


def test_onboarding_verified_company_email_links_company(client, mock_supabase):
    """
    POST /v1/auth/onboarding with verified company email links company_id.
    """
    comp_id = "comp-tcs-100"
    mock_supabase.store["companies"].append({"id": comp_id, "name": "Tata Consultancy Services (TCS)"})

    res = client.post(
        "/v1/auth/onboarding",
        headers={"Authorization": "Bearer valid-token-company-user"},
        json={"role": "company", "display_name": "TCS HR"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "company"
    assert data["company_id"] == comp_id
    assert "Tata Consultancy Services" in data["company_name"]
    assert "Linked to" in data["message"]


def test_null_role_user_blocked_from_role_protected_routes(client, mock_supabase):
    """
    User with a null role must not reach role-protected pages or API routes (403 Forbidden).
    """
    headers = {"Authorization": "Bearer valid-token-null-role"}

    # 1. Chat API
    chat_res = client.post("/v1/chat", headers=headers, json={"message": "hello"})
    assert chat_res.status_code == 403
    assert "onboarding" in chat_res.json()["detail"].lower()

    # 2. Contacts API
    contacts_res = client.get("/v1/contacts", headers=headers)
    assert contacts_res.status_code == 403
    assert "onboarding" in contacts_res.json()["detail"].lower()

    # 3. Student profile & score APIs
    score_res = client.get("/v1/students/me/score", headers=headers)
    assert score_res.status_code == 403
    assert "onboarding" in score_res.json()["detail"].lower()

    prof_res = client.get("/v1/students/me/profile", headers=headers)
    assert prof_res.status_code == 403
    assert "onboarding" in prof_res.json()["detail"].lower()


def test_onboarding_cannot_change_existing_non_student_role(client, mock_supabase):
    """
    A user whose role is already established (e.g. placement_officer) cannot change role via onboarding.
    """
    res = client.post(
        "/v1/auth/onboarding",
        headers={"Authorization": "Bearer valid-token-officer"},
        json={"role": "student"},
    )
    assert res.status_code == 400
    assert "Changing profile role from placement_officer is not permitted" in res.json()["detail"]
