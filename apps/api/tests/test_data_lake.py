import uuid
from datetime import datetime, timezone

from app.db.seed import seed_data
from app.search.data_lake import search_data_lake


def test_search_data_lake_finds_matches(mock_supabase):
    seed_data(mock_supabase)
    actor_id = "recruiter-456"

    # Search for campus recruiters at TCS
    result = search_data_lake(
        mock_supabase,
        query="campus recruiters TCS",
        actor_id=actor_id,
    )

    assert result["found"] > 0
    assert len(result["contacts"]) > 0

    contact_names = [c["name"] for c in result["contacts"]]
    assert any("Aarav Sharma" in n for n in contact_names)

    # Check raw_events audit row was written
    search_events = [
        ev
        for ev in mock_supabase.store["raw_events"]
        if ev.get("source") == "search" and ev.get("actor_id") == actor_id
    ]
    assert len(search_events) >= 1
    ev_payload = search_events[0]["payload"]
    assert ev_payload["kind"] == "data_lake"
    assert ev_payload["found"] == result["found"]


def test_search_data_lake_excludes_suppressed(mock_supabase):
    # Insert normal contact and suppressed contact
    normal_id = str(uuid.uuid4())
    suppressed_id = str(uuid.uuid4())

    mock_supabase.store["contacts"].extend(
        [
            {
                "id": normal_id,
                "name": "Visible Leader",
                "title": "Recruiter",
                "role_type": "recruiter",
                "suppressed_at": None,
            },
            {
                "id": suppressed_id,
                "name": "Suppressed Person",
                "title": "Recruiter",
                "role_type": "recruiter",
                "suppressed_at": datetime.now(timezone.utc).isoformat(),
            },
        ]
    )

    # Search specifically for "Suppressed Person"
    res = search_data_lake(mock_supabase, query="Suppressed Person")
    assert all(c["id"] != suppressed_id for c in res["contacts"])

    # Search generally
    res_all = search_data_lake(mock_supabase, query="Visible Leader")
    assert any(c["id"] == normal_id for c in res_all["contacts"])


def test_search_data_lake_filters(mock_supabase):
    seed_data(mock_supabase)

    # Filter strictly by placement_officer
    res = search_data_lake(
        mock_supabase,
        query="placements",
        filters={"role_type": "placement_officer"},
    )
    assert res["found"] > 0
    for c in res["contacts"]:
        assert c["role_type"] == "placement_officer"
