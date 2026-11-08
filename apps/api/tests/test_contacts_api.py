import uuid
from datetime import datetime, timezone


def test_list_contacts_basic_and_filters(client, mock_supabase):
    c1_id = str(uuid.uuid4())
    comp_id = str(uuid.uuid4())
    coll_id = str(uuid.uuid4())

    mock_supabase.store["companies"].append(
        {"id": comp_id, "name": "Tata Consultancy Services", "category": "enterprise"}
    )
    mock_supabase.store["colleges"].append({"id": coll_id, "name": "VJTI Mumbai", "city": "Mumbai"})
    mock_supabase.store["contacts"].extend(
        [
            {
                "id": c1_id,
                "name": "Aarav Patel",
                "title": "Lead Campus Recruiter",
                "company_id": comp_id,
                "college_id": None,
                "role_type": "campus_recruiter",
                "email": "aarav.patel@tcs.com",
                "linkedin_url": "https://linkedin.com/in/aaravpatel",
                "suppressed_at": None,
                "source": "web",
                "source_url": "https://tcs.com/careers",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Sunita Rao",
                "title": "TPO Officer",
                "company_id": None,
                "college_id": coll_id,
                "role_type": "placement_officer",
                "email": "sunita@vjti.ac.in",
                "suppressed_at": None,
                "source": "seed",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Hidden Contact",
                "title": "Recruiter",
                "company_id": comp_id,
                "college_id": None,
                "role_type": "campus_recruiter",
                "email": "hidden@tcs.com",
                "suppressed_at": datetime.now(timezone.utc).isoformat(),
                "source": "seed",
            },
        ]
    )

    # 1. Basic list without filters - should return 2 active contacts, excluding the suppressed one
    res = client.get(
        "/v1/contacts",
        headers={"Authorization": "Bearer valid-token-recruiter"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    names = [c["name"] for c in data["items"]]
    assert "Aarav Patel" in names
    assert "Sunita Rao" in names
    assert "Hidden Contact" not in names

    # Verify company_name and college_name resolved
    aarav = next(c for c in data["items"] if c["name"] == "Aarav Patel")
    assert aarav["company_name"] == "Tata Consultancy Services"
    assert aarav["role_type"] == "campus_recruiter"
    assert len(aarav["sources"]) >= 1
    assert aarav["sources"][0]["domain"] == "tcs.com"

    # 2. Filter by q
    res_q = client.get(
        "/v1/contacts?q=Aarav",
        headers={"Authorization": "Bearer valid-token-recruiter"},
    )
    assert res_q.status_code == 200
    assert res_q.json()["total"] == 1
    assert res_q.json()["items"][0]["name"] == "Aarav Patel"

    # 3. Filter by role_type
    res_role = client.get(
        "/v1/contacts?role_type=placement_officer",
        headers={"Authorization": "Bearer valid-token-recruiter"},
    )
    assert res_role.status_code == 200
    assert res_role.json()["total"] == 1
    assert res_role.json()["items"][0]["name"] == "Sunita Rao"


def test_save_and_delete_contact(client, mock_supabase):
    cid = str(uuid.uuid4())
    mock_supabase.store["contacts"].append(
        {
            "id": cid,
            "name": "Vikram Singh",
            "title": "Talent Acquisition",
            "suppressed_at": None,
            "source": "seed",
        }
    )

    headers = {"Authorization": "Bearer valid-token-recruiter"}

    # Initially not saved
    res = client.get("/v1/contacts?q=Vikram", headers=headers)
    assert res.status_code == 200
    assert res.json()["items"][0]["saved"] is False

    # POST /v1/contacts/{id}/save with user-provided phone
    save_res = client.post(
        f"/v1/contacts/{cid}/save",
        json={"phone": "+91 98765 43210"},
        headers=headers,
    )
    assert save_res.status_code == 200
    assert save_res.json() == {"contact_id": cid, "saved": True}

    # Verify user_saved_contacts row contains the phone
    saved_rows = mock_supabase.store["user_saved_contacts"]
    assert len(saved_rows) == 1
    assert saved_rows[0]["contact_id"] == cid
    assert saved_rows[0]["profile_id"] == "recruiter-456"
    assert saved_rows[0]["phone"] == "+91 98765 43210"

    # Lake contact has NO phone added
    lake_contact = mock_supabase.store["contacts"][0]
    assert lake_contact.get("phone") is None or lake_contact.get("phone") == ""

    # Verify contacts list now reports saved=True
    res2 = client.get("/v1/contacts?q=Vikram", headers=headers)
    assert res2.json()["items"][0]["saved"] is True

    # Verify saved_only=True returns this contact
    saved_only_res = client.get("/v1/contacts?saved_only=true", headers=headers)
    assert saved_only_res.status_code == 200
    assert saved_only_res.json()["total"] == 1
    assert saved_only_res.json()["items"][0]["id"] == cid

    # Another user does not have it saved
    other_headers = {"Authorization": "Bearer valid-token-student"}
    res_other = client.get("/v1/contacts?saved_only=true", headers=other_headers)
    assert res_other.status_code == 200
    assert res_other.json()["total"] == 0

    # DELETE /v1/contacts/{id}/save
    del_res = client.delete(f"/v1/contacts/{cid}/save", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json() == {"contact_id": cid, "saved": False}

    # Lake contact is NOT deleted
    assert len(mock_supabase.store["contacts"]) == 1
    assert mock_supabase.store["contacts"][0]["id"] == cid

    # user_saved_contacts is now empty for this user
    assert len(mock_supabase.store["user_saved_contacts"]) == 0


def test_agent_runs_endpoint(client, mock_supabase):
    run_id = str(uuid.uuid4())
    mock_supabase.store["agent_runs"].append(
        {
            "id": run_id,
            "profile_id": "recruiter-456",
            "status": "completed",
            "steps": [
                {"type": "tool_call", "tool": "search_data_lake", "found": 3},
                {
                    "type": "search_summary",
                    "summary": "searched data lake, found 3; searched web, found 2; added 1 new, merged 2",
                },
            ],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    headers = {"Authorization": "Bearer valid-token-recruiter"}

    res = client.get(f"/v1/agent-runs/{run_id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == run_id
    assert data["status"] == "completed"
    assert len(data["steps"]) == 2
    assert data["summary"] == "searched data lake, found 3; searched web, found 2; added 1 new, merged 2"

    # 404 for unknown run
    bad_res = client.get(f"/v1/agent-runs/{uuid.uuid4()}", headers=headers)
    assert bad_res.status_code == 404

    # 403 for run belonging to another user
    other_headers = {"Authorization": "Bearer valid-token-student"}
    forbidden_res = client.get(f"/v1/agent-runs/{run_id}", headers=other_headers)
    assert forbidden_res.status_code == 403
