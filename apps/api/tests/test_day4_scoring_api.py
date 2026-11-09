from unittest.mock import MagicMock

import pytest

from app.db.schema_check import MissingMigrationError, check_database_schema


def test_schema_check_names_005_day4_roles(monkeypatch):
    """Probe missing student_records/campus_hiring table triggers MissingMigrationError naming 005_day4_roles.sql."""
    monkeypatch.setattr("app.db.schema_check.should_skip_schema_check", lambda: False)
    mock_client = MagicMock()

    def table_router(name):
        # Day 3 tables pass
        if name in ("contact_sources", "contacts", "search_cache", "user_saved_contacts"):
            m = MagicMock()
            m.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
            return m
        # Day 4 table fails
        raise Exception("table student_records does not exist")

    mock_client.table.side_effect = table_router

    with pytest.raises(MissingMigrationError) as exc_info:
        check_database_schema(client=mock_client, raise_on_error=True)

    err = str(exc_info.value)
    assert "005_day4_roles.sql" in err
    assert "student_records" in err


def test_get_college_score_endpoint(client, mock_supabase):
    college_id = "col-mumbai-1"
    comp_id = "comp-morgan"

    mock_supabase.store["companies"].append({"id": comp_id, "name": "Morgan Stanley", "category": "investment_bank"})
    mock_supabase.store["campus_hiring"].extend(
        [
            {
                "id": "ch-1",
                "college_id": college_id,
                "company_id": comp_id,
                "cycle_year": 2027,
                "type": "full_time",
                "offers_made": 8,
            },
            {
                "id": "ch-2",
                "college_id": college_id,
                "company_id": comp_id,
                "cycle_year": 2027,
                "type": "internship",
                "offers_made": 7,
            },
        ]
    )

    response = client.get(
        f"/v1/colleges/{college_id}/score",
        headers={"Authorization": "Bearer valid-token-officer"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["campus_score"] == 53  # 50 + 3
    assert data["campus_internship_score"] == 53  # 50 + 3
    assert len(data["breakdown"]) >= 1
    assert data["flagged"] == []


def test_get_company_score_endpoint(client, mock_supabase):
    comp_id = "comp-tcs-1"
    mock_supabase.store["campus_hiring"].append(
        {
            "id": "ch-comp-1",
            "company_id": comp_id,
            "college_id": "col-1",
            "cycle_year": 2027,
            "type": "full_time",
            "offers_made": 15,
        }
    )

    response = client.get(
        f"/v1/companies/{comp_id}/score",
        headers={"Authorization": "Bearer valid-token-company"},
    )
    assert response.status_code == 200
    data = response.json()
    # 50 base + 2 (10-20 offers) = 52
    assert data["score"] == 52
    assert len(data["breakdown"]) >= 2
