import uuid

from app.main import app


def test_draft_outreach_email(client, mock_supabase):
    contact_id = str(uuid.uuid4())
    mock_supabase.store["contacts"].append(
        {
            "id": contact_id,
            "name": "Aarav Sharma",
            "title": "Lead Campus Recruiter",
            "role_type": "campus_recruiter",
            "email": "aarav@tcs.example.com",
        }
    )

    resp = client.post(
        "/v1/outreach/draft",
        json={
            "contact_id": contact_id,
            "channel": "email",
            "sender_context": "Focus on SDE roles for 2027 batch",
        },
        headers={"Authorization": "Bearer valid-token-recruiter"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "draft_id" in data
    assert data["channel"] == "email"
    assert data["subject"] is not None
    assert "SDE" in data["body"] or "2027" in data["body"] or "campus" in data["body"].lower()
    assert "Aarav" in data["body"]

    # Verify draft saved in private outreach_drafts table
    saved_drafts = mock_supabase.store["outreach_drafts"]
    assert len(saved_drafts) == 1
    draft_row = saved_drafts[0]
    assert draft_row["id"] == data["draft_id"]
    assert draft_row["profile_id"] == "recruiter-456"
    assert draft_row["contact_id"] == contact_id


def test_draft_outreach_linkedin(client, mock_supabase):
    contact_id = str(uuid.uuid4())
    mock_supabase.store["contacts"].append(
        {
            "id": contact_id,
            "name": "Prof. Rajesh Patil",
            "title": "Training & Placement Officer",
            "role_type": "placement_officer",
        }
    )

    resp = client.post(
        "/v1/outreach/draft",
        json={
            "contact_id": contact_id,
            "channel": "linkedin",
        },
        headers={"Authorization": "Bearer valid-token-recruiter"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["channel"] == "linkedin"
    assert data["subject"] is None
    assert "Rajesh" in data["body"] or "Patil" in data["body"]
    assert len(data["body"]) < 400


def test_no_send_path_exists():
    """Hard rule: draft_outreach never sends anything. There is no send endpoint."""
    openapi_paths = list(app.openapi().get("paths", {}).keys())
    send_endpoints = [p for p in openapi_paths if "send" in p.lower()]
    assert len(send_endpoints) == 0, f"Found forbidden send endpoint: {send_endpoints}"
