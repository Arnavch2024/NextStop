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
