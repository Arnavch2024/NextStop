import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.search.data_lake import search_data_lake


def test_privacy_doc_exists_and_covers_process():
    doc_path = Path(__file__).resolve().parents[3] / "docs" / "privacy.md"
    assert doc_path.exists(), "docs/privacy.md must exist"
    content = doc_path.read_text(encoding="utf-8")
    assert "Intake" in content
    assert "Review" in content
    assert "Action" in content
    assert "Confirmation" in content
    assert "Logging" in content
    assert "suppressed_at" in content
    assert "legal compliance" in content.lower()
    assert "not" in content.lower()


def test_contact_suppression_removes_from_all_reads(client, mock_supabase):
    cid = str(uuid.uuid4())
    comp_id = str(uuid.uuid4())

    mock_supabase.store["companies"].append({"id": comp_id, "name": "Infosys BPM", "category": "enterprise"})
    mock_supabase.store["contacts"].append(
        {
            "id": cid,
            "name": "Manish Sharma",
            "title": "Senior Campus Recruiter",
            "company_id": comp_id,
            "role_type": "campus_recruiter",
            "email": "manish.sharma@infosys.com",
            "suppressed_at": None,
            "source": "seed",
        }
    )

    headers = {"Authorization": "Bearer valid-token-recruiter"}

    # 1. Initially appears in search_data_lake
    lake_res = search_data_lake(mock_supabase, query="Manish", actor_id="recruiter-456")
    assert lake_res["found"] == 1
    assert lake_res["contacts"][0]["id"] == cid

    # 2. Initially appears in GET /v1/contacts
    api_res = client.get("/v1/contacts?q=Manish", headers=headers)
    assert api_res.status_code == 200
    assert api_res.json()["total"] == 1
    assert api_res.json()["items"][0]["id"] == cid

    # 3. User saves the contact
    save_res = client.post(f"/v1/contacts/{cid}/save", headers=headers)
    assert save_res.status_code == 200

    saved_list_res = client.get("/v1/contacts?saved_only=true", headers=headers)
    assert saved_list_res.status_code == 200
    assert saved_list_res.json()["total"] == 1

    # 4. Operator sets suppressed_at = now()
    now_iso = datetime.now(timezone.utc).isoformat()
    mock_supabase.table("contacts").update({"suppressed_at": now_iso}).eq("id", cid).execute()

    # 5. Immediately hidden from search_data_lake
    lake_res_after = search_data_lake(mock_supabase, query="Manish", actor_id="recruiter-456")
    assert lake_res_after["found"] == 0

    # 6. Immediately hidden from GET /v1/contacts (both standard and saved_only)
    api_res_after = client.get("/v1/contacts?q=Manish", headers=headers)
    assert api_res_after.status_code == 200
    assert api_res_after.json()["total"] == 0

    saved_list_after = client.get("/v1/contacts?saved_only=true", headers=headers)
    assert saved_list_after.status_code == 200
    assert saved_list_after.json()["total"] == 0
