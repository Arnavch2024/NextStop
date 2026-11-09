import uuid
from unittest.mock import MagicMock, patch

import pytest
from google.genai import types

from app.models.db import ProfileRole, UserProfile
from app.search.data_lake import search_data_lake
from app.search.dedupe import upsert_contact


def make_gemini_tool_call_response(tool_name: str, args: dict):
    fc = types.FunctionCall(name=tool_name, args=args)
    content = types.Content(role="model", parts=[types.Part(function_call=fc)])
    candidate = types.Candidate(content=content)
    return types.GenerateContentResponse(candidates=[candidate])


def make_gemini_text_response(text: str):
    content = types.Content(role="model", parts=[types.Part.from_text(text=text)])
    candidate = types.Candidate(content=content)
    return types.GenerateContentResponse(candidates=[candidate])


def test_contact_field_persistence_upsert_and_read_back(client, mock_supabase):
    """Item 1: Write candidate through real upsert path, read it back via data lake and API, assert every field."""
    company_id = str(uuid.uuid4())
    mock_supabase.store["companies"].append(
        {"id": company_id, "name": "JP Morgan Chase Global Technology", "category": "GCC"}
    )

    admin_user = UserProfile(
        id=str(uuid.uuid4()),
        role=ProfileRole.RECRUITER,
        display_name="Test Ingest Admin",
    )

    candidate = {
        "name": "Savit Anand",
        "title": "Executive Director, Recruiting",
        "company_id": company_id,
        "company": "JP Morgan Chase Global Technology",
        "location": "Mumbai",
        "source_url": "https://linkedin.com/in/savitanand",
        "published_date": "2026-09-22",
        "stale": False,
        "confidence": 0.6,
        "unverified": True,
        "fetch_status": "not_fetched",
        "verified": False,
    }

    upsert_res = upsert_contact(
        mock_supabase,
        candidate,
        admin_user,
        source="web",
        source_url="https://linkedin.com/in/savitanand",
    )
    assert upsert_res["op"] == "created"
    contact_id = upsert_res["contact_id"]

    # 1. Read back via search_data_lake
    lake_res = search_data_lake(mock_supabase, query="Savit Anand", include_sample=True)
    assert lake_res["found"] == 1
    c_lake = lake_res["contacts"][0]

    assert c_lake["id"] == contact_id
    assert c_lake["name"] == "Savit Anand"
    assert c_lake["title"] == "Executive Director, Recruiting"
    assert c_lake["company_name"] == "JP Morgan Chase Global Technology"
    assert c_lake["location"] == "Mumbai"
    assert c_lake["source"] == "web"
    assert c_lake["source_url"] == "https://linkedin.com/in/savitanand"
    assert c_lake["source_published_date"] == "2026-09-22"
    assert c_lake["stale"] is False
    assert abs(c_lake["confidence"] - 0.6) < 1e-4
    assert c_lake["unverified"] is True

    # 2. Read back via GET /v1/contacts
    http_res = client.get(
        "/v1/contacts?q=Savit+Anand&include_sample=true",
        headers={"Authorization": "Bearer valid-token-student"},
    )
    assert http_res.status_code == 200
    data = http_res.json()
    assert data["total"] == 1
    c_api = data["items"][0]

    assert c_api["id"] == contact_id
    assert c_api["name"] == "Savit Anand"
    assert c_api["title"] == "Executive Director, Recruiting"
    assert c_api["company_name"] == "JP Morgan Chase Global Technology"
    assert c_api["location"] == "Mumbai"
    assert c_api["source"] == "web"
    assert c_api["source_url"] == "https://linkedin.com/in/savitanand"
    assert c_api["source_published_date"] == "2026-09-22"
    assert c_api["stale"] is False
    assert abs(c_api["confidence"] - 0.6) < 1e-4
    assert c_api["unverified"] is True


def test_chat_cannot_create_snippet_candidate_failing_rule_a(client, mock_supabase):
    """Item 2: Snippet-derived candidate that fails rule (a) cannot be created from chat."""
    company_id = str(uuid.uuid4())
    mock_supabase.store["companies"].append(
        {"id": company_id, "name": "Barclays Global Service Centre", "category": "GCC"}
    )

    # Gemini attempts to call upsert_contact with a person where company does not match sentence
    tool_args = {
        "name": "Akhlaque Qamar",
        "title": "Assistant Vice President",
        "company": "Barclays Global Service Centre",
        "source": "web",
        "source_url": "https://linkedin.com/in/akhlaque",
        "snippet": "Akhlaque Qamar joined another institution in Pune.",  # Fails rule (a)
    }

    mock_gemini = MagicMock()
    mock_gemini.models.generate_content.side_effect = [
        make_gemini_tool_call_response("upsert_contact", tool_args),
        make_gemini_text_response("Could not add recruiter because company check failed."),
    ]

    initial_count = len(mock_supabase.store["contacts"])
    with patch("app.agent.runner.get_gemini_client", return_value=mock_gemini):
        res = client.post(
            "/v1/chat",
            headers={"Authorization": "Bearer valid-token-student"},
            json={"message": "Can you add this recruiter?"},
        )

    assert res.status_code == 200
    # Assert contact was NOT created
    assert len(mock_supabase.store["contacts"]) == initial_count
    # Check that tool returned precision error
    events = mock_supabase.store["raw_events"]
    tool_results = [e["payload"]["result"] for e in events if e.get("source") == "tool_result"]
    assert any("precision_rule_failed" in str(r.get("error", "")) for r in tool_results)


def test_chat_creates_snippet_candidate_passing_rules_with_unverified_flag(client, mock_supabase):
    """Item 2: Candidate passing rules (a) and (b) is created with source_url and unverified flag."""
    company_id = str(uuid.uuid4())
    mock_supabase.store["companies"].append(
        {"id": company_id, "name": "Barclays Global Service Centre", "category": "GCC"}
    )

    tool_args = {
        "name": "Vikas Sharma",
        "title": "Vice President Talent Acquisition",
        "company": "Barclays Global Service Centre",
        "source": "web",
        "source_url": "https://linkedin.com/in/vikas-sharma",
        "snippet": "Vikas Sharma is Vice President Talent Acquisition at Barclays Global Service Centre in Mumbai.",
    }

    mock_gemini = MagicMock()
    mock_gemini.models.generate_content.side_effect = [
        make_gemini_tool_call_response("upsert_contact", tool_args),
        make_gemini_text_response("Added Vikas Sharma."),
    ]

    with patch("app.agent.runner.get_gemini_client", return_value=mock_gemini):
        res = client.post(
            "/v1/chat",
            headers={"Authorization": "Bearer valid-token-student"},
            json={"message": "Found Vikas Sharma at Barclays."},
        )

    assert res.status_code == 200
    created = [c for c in mock_supabase.store["contacts"] if c.get("name") == "Vikas Sharma"]
    assert len(created) == 1
    assert created[0]["source_url"] == "https://linkedin.com/in/vikas-sharma"
    sources = [s for s in mock_supabase.store["contact_sources"] if s.get("contact_id") == created[0]["id"]]
    assert len(sources) >= 1
    assert sources[0]["unverified"] is True


def test_suppressed_contacts_excluded_from_search_and_api(client, mock_supabase):
    """Item 3: Suppressed contacts are excluded from search_data_lake and GET /v1/contacts."""
    company_id = str(uuid.uuid4())
    mock_supabase.store["companies"].append({"id": company_id, "name": "Test Co", "category": "GCC"})

    active_id = str(uuid.uuid4())
    suppressed_id = str(uuid.uuid4())

    mock_supabase.store["contacts"].append(
        {
            "id": active_id,
            "name": "Active Recruiter",
            "title": "Campus Lead",
            "company_id": company_id,
            "suppressed_at": None,
            "source": "web",
        }
    )
    mock_supabase.store["contacts"].append(
        {
            "id": suppressed_id,
            "name": "Suppressed Recruiter",
            "title": "Old Lead",
            "company_id": company_id,
            "suppressed_at": "2026-11-08T00:00:00Z",
            "source": "web",
        }
    )

    # Direct data lake search
    res = search_data_lake(mock_supabase, query="Recruiter", include_sample=True)
    ids = [c["id"] for c in res["contacts"]]
    assert active_id in ids
    assert suppressed_id not in ids

    # HTTP API
    http_res = client.get(
        "/v1/contacts?q=Recruiter&include_sample=true",
        headers={"Authorization": "Bearer valid-token-student"},
    )
    assert http_res.status_code == 200
    api_ids = [c["id"] for c in http_res.json()["items"]]
    assert active_id in api_ids
    assert suppressed_id not in api_ids


def test_chat_search_reply_lists_contacts_and_never_says_recorded_details(client, mock_supabase):
    """Item 4: Search reply lists contacts with details and never says 'I've recorded your details'."""
    company_id = str(uuid.uuid4())
    mock_supabase.store["companies"].append(
        {"id": company_id, "name": "JP Morgan Chase Global Technology", "category": "GCC"}
    )
    mock_supabase.store["contacts"].append(
        {
            "id": str(uuid.uuid4()),
            "name": "Savit Anand",
            "title": "Executive Director, Recruiting",
            "company_id": company_id,
            "location": "Mumbai",
            "source": "web",
            "source_published_date": "2026-09-22",
            "suppressed_at": None,
        }
    )

    # Case A: LLM returns tool call then empty text (or misdirected text)
    mock_gemini = MagicMock()
    mock_gemini.models.generate_content.side_effect = [
        make_gemini_tool_call_response("search_data_lake", {"query": "JP Morgan"}),
        make_gemini_text_response("I've recorded your details successfully. Let me know if you need anything else!"),
    ]

    with patch("app.agent.runner.get_gemini_client", return_value=mock_gemini):
        res = client.post(
            "/v1/chat",
            headers={"Authorization": "Bearer valid-token-student"},
            json={"message": "Which GCCs in Mumbai hire from campus and who are the recruiters?"},
        )

    assert res.status_code == 200
    data = res.json()
    reply = data["reply"]
    assert "recorded your details" not in reply.lower()
    assert "Savit Anand" in reply
    assert "JP Morgan Chase Global Technology" in reply


def test_startup_schema_check_names_missing_migration(monkeypatch):
    """Startup schema check raises MissingMigrationError naming the missing migration on error."""
    monkeypatch.setattr("app.db.schema_check.should_skip_schema_check", lambda: False)
    from app.db.schema_check import MissingMigrationError, check_database_schema

    mock_client = MagicMock()
    mock_client.table.side_effect = Exception("table public.contact_sources does not exist")

    with pytest.raises(MissingMigrationError) as exc_info:
        check_database_schema(client=mock_client, raise_on_error=True)

    err = str(exc_info.value)
    assert "003_search_slice.sql" in err
    assert "contact_sources" in err
