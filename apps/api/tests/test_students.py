import pytest
from app.models.db import ProfileRole, UserProfile


def test_score_endpoint_returns_base_score(client, mock_supabase):
    response = client.get(
        "/v1/students/me/score",
        headers={"Authorization": "Bearer valid-token-student"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 20
    assert len(data["breakdown"]) == 1
    assert data["breakdown"][0]["reason"] == "Base score"
    assert data["breakdown"][0]["points"] == 20
    assert len(data["next_best_actions"]) > 0

    # Ensure a score_events row was recorded in DB
    events = mock_supabase.store["score_events"]
    assert len(events) == 1
    assert events[0]["score"] == 20


def test_profile_endpoint_returns_empty_lists(client, mock_supabase):
    response = client.get(
        "/v1/students/me/profile",
        headers={"Authorization": "Bearer valid-token-student"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["student"] is None or isinstance(data["student"], dict)
    assert data["education"] == []
    assert data["internships"] == []
    assert data["jobs"] == []
    assert data["skills"] == []
    assert data["documents"] == []


def test_score_endpoint_reflects_score_event_history(client, mock_supabase):
    # Setup student
    student_id = "student-test-123"
    mock_supabase.store["students"].append({
        "id": student_id,
        "profile_id": "user-123",
        "full_name": "Riya Sharma",
        "batch_year": 2027,
    })
    # Add education
    mock_supabase.store["education"].append({
        "id": "edu-1",
        "student_id": student_id,
        "profile_id": "user-123",
        "level": "twelfth",
        "score_value": 92.0,
        "score_scale": "percentage",
        "source": "resume",
    })

    # Call /score -> computes and stores event
    res = client.get(
        "/v1/students/me/score",
        headers={"Authorization": "Bearer valid-token-student"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["score"] == 21  # 20 base + 1 hs

    # Verify score_events has a record
    assert len(mock_supabase.store["score_events"]) == 1
    assert mock_supabase.store["score_events"][0]["score"] == 21

    # Verify profile endpoint returns education
    prof_res = client.get(
        "/v1/students/me/profile",
        headers={"Authorization": "Bearer valid-token-student"},
    )
    assert prof_res.status_code == 200
    pdata = prof_res.json()
    assert len(pdata["education"]) == 1
    assert pdata["education"][0]["level"] == "twelfth"

