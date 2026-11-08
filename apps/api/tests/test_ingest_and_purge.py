import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models.db import ProfileRole, UserProfile
from app.search.data_lake import search_data_lake
from app.search.extract_contacts import CandidateContact
from app.search.ingest import run_ingest
from app.search.providers.base import SearchResult
from app.search.purge import run_purge


@pytest.fixture
def test_user():
    return UserProfile(
        id=str(uuid.uuid4()),
        role=ProfileRole.RECRUITER,
        display_name="Test Ingest Admin",
        email="admin@test.local",
    )


def test_ingest_adds_merges_drops_nameless_and_never_stores_phone(mock_supabase, test_user):
    # Setup company
    company_id = str(uuid.uuid4())
    mock_supabase.store["companies"].append({"id": company_id, "name": "Barclays India", "category": "GCC"})

    # Pre-existing contact for Barclays to test merging
    existing_id = str(uuid.uuid4())
    mock_supabase.store["contacts"].append(
        {
            "id": existing_id,
            "name": "Priya Deshmukh",
            "title": "Junior Recruiter",
            "company_id": company_id,
            "linkedin_url": "https://linkedin.com/in/priyadeshmukh",
            "source": "seed",
        }
    )

    # Mock search provider returning 2 results
    mock_search_provider = MagicMock()
    mock_search_provider.search.return_value = [
        SearchResult(
            title="Barclays India Campus Team",
            url="https://barclays.example.com/careers",
            snippet="Meet our recruitment leads",
        ),
        SearchResult(
            title="Priya Deshmukh - Barclays LinkedIn",
            url="https://linkedin.com/in/priyadeshmukh",
            snippet="Lead Campus Recruiter at Barclays India",
        ),
    ]

    # Mock LLM provider returning:
    # 1. New contact (with phone that must be stripped)
    # 2. Merging contact (Priya)
    # 3. Nameless candidate (should be dropped)
    candidate_new = CandidateContact(
        name="Rohit Verma",
        title="University Relations Lead",
        company="Barclays India",
        linkedin_url="https://linkedin.com/in/rohitverma",
        email="rohit.v@barclays.example.com",
        source_url="https://barclays.example.com/careers",
    )
    candidate_merge = CandidateContact(
        name="Priya Deshmukh",
        title="Lead Campus Recruiter",
        company="Barclays India",
        linkedin_url="https://linkedin.com/in/priyadeshmukh",
        email="priya.d@barclays.example.com",
        source_url="https://linkedin.com/in/priyadeshmukh",
    )
    candidate_nameless = CandidateContact(
        name="",  # nameless
        title="HR Manager",
    )

    # extract_contacts_from_text will be mocked to return these
    with patch(
        "app.search.ingest.extract_contacts_from_text",
        side_effect=[
            [candidate_new, candidate_nameless],
            [candidate_merge],
        ],
    ):
        stats = run_ingest(
            client=mock_supabase,
            category="GCC",
            limit=5,
            delay=0,
            dry_run=False,
            search_provider=mock_search_provider,
            admin_user=test_user,
        )

    assert stats["companies_processed"] == 1
    assert stats["contacts_added"] == 1
    assert stats["contacts_merged"] == 1
    assert stats["contacts_dropped"] == 1
    assert stats["errors"] == 0

    # Verify newly created contact has source='web' and NO phone
    contacts = mock_supabase.store["contacts"]
    rohit = next((c for c in contacts if c.get("name") == "Rohit Verma"), None)
    assert rohit is not None
    assert rohit.get("source") == "web"
    assert "phone" not in rohit or rohit.get("phone") is None

    # Verify merged contact was updated to source='web'
    priya = next((c for c in contacts if c.get("name") == "Priya Deshmukh"), None)
    assert priya is not None
    assert priya.get("title") == "Lead Campus Recruiter"
    assert priya.get("source") == "web"
    assert "phone" not in priya or priya.get("phone") is None


def test_ingest_handles_quota_errors_cleanly(mock_supabase, test_user):
    mock_supabase.store["companies"].append({"id": str(uuid.uuid4()), "name": "Company A", "category": "GCC"})
    mock_supabase.store["companies"].append({"id": str(uuid.uuid4()), "name": "Company B", "category": "GCC"})

    mock_search_provider = MagicMock()
    mock_search_provider.search.side_effect = Exception("429 Resource exhausted: Quota exceeded")

    stats = run_ingest(
        client=mock_supabase,
        category="GCC",
        limit=5,
        delay=0,
        dry_run=False,
        search_provider=mock_search_provider,
        admin_user=test_user,
    )

    # Should stop cleanly on first 429
    assert stats["errors"] == 1
    assert stats["companies_processed"] == 0
    assert stats["contacts_added"] == 0


def test_ingest_dry_run_writes_nothing(mock_supabase, test_user):
    company_id = str(uuid.uuid4())
    mock_supabase.store["companies"].append({"id": company_id, "name": "Morgan Stanley", "category": "GCC"})

    initial_contacts_count = len(mock_supabase.store["contacts"])
    initial_sources_count = len(mock_supabase.store["contact_sources"])

    mock_search_provider = MagicMock()
    mock_search_provider.search.return_value = [
        SearchResult(
            title="Morgan Stanley Careers",
            url="https://morganstanley.example.com/recruiting",
            snippet="Recruiting Team Mumbai",
        )
    ]

    candidate = CandidateContact(
        name="Anjali Nair",
        title="Head of Campus Recruiting",
        company="Morgan Stanley",
        linkedin_url="https://linkedin.com/in/anjalinair",
        source_url="https://morganstanley.example.com/recruiting",
    )

    with patch(
        "app.search.ingest.extract_contacts_from_text",
        return_value=[candidate],
    ):
        stats = run_ingest(
            client=mock_supabase,
            category="GCC",
            delay=0,
            dry_run=True,
            search_provider=mock_search_provider,
            admin_user=test_user,
        )

    # Dry-run records what would be added
    assert stats["contacts_added"] == 1
    assert stats["companies_processed"] == 1

    # Absolute guarantee: no database writes occurred!
    assert len(mock_supabase.store["contacts"]) == initial_contacts_count
    assert len(mock_supabase.store["contact_sources"]) == initial_sources_count


def test_purge_seed_deletes_only_seed_rows(mock_supabase):
    seed_c_id = str(uuid.uuid4())
    web_c_id = str(uuid.uuid4())

    mock_supabase.store["contacts"].append({"id": seed_c_id, "name": "Seed Contact", "source": "seed"})
    mock_supabase.store["contacts"].append({"id": web_c_id, "name": "Real Web Contact", "source": "web"})

    mock_supabase.store["contact_sources"].append({"id": str(uuid.uuid4()), "contact_id": seed_c_id, "source": "seed"})
    mock_supabase.store["contact_sources"].append({"id": str(uuid.uuid4()), "contact_id": web_c_id, "source": "web"})

    # 1. Unconfirmed purge should delete 0
    res_dry = run_purge(client=mock_supabase, confirm=False)
    assert res_dry["contacts_found"] == 1
    assert res_dry["sources_found"] == 1
    assert res_dry["contacts_deleted"] == 0
    assert len(mock_supabase.store["contacts"]) == 2

    # 2. Confirmed purge should delete only seed rows
    res_confirmed = run_purge(client=mock_supabase, confirm=True)
    assert res_confirmed["contacts_deleted"] == 1
    assert res_confirmed["sources_deleted"] == 1

    # Real web contact and its source remain intact
    remaining_contacts = mock_supabase.store["contacts"]
    assert len(remaining_contacts) == 1
    assert remaining_contacts[0]["id"] == web_c_id
    assert remaining_contacts[0]["source"] == "web"

    remaining_sources = mock_supabase.store["contact_sources"]
    assert len(remaining_sources) == 1
    assert remaining_sources[0]["contact_id"] == web_c_id


def test_ordering_and_include_sample_flag(mock_supabase, client, monkeypatch):
    real_contact_id = str(uuid.uuid4())
    seed_contact_id = str(uuid.uuid4())

    mock_supabase.store["contacts"].append(
        {
            "id": seed_contact_id,
            "name": "Aarav Seed",
            "title": "Campus Recruiter",
            "source": "seed",
        }
    )
    mock_supabase.store["contacts"].append(
        {
            "id": real_contact_id,
            "name": "Zoya Real",
            "title": "Campus Recruiter",
            "source": "web",
        }
    )

    # 1. When DEMO_SHOW_SAMPLE is false:
    monkeypatch.setenv("DEMO_SHOW_SAMPLE", "false")

    # search_data_lake default excludes sample
    res_default = search_data_lake(client=mock_supabase)
    default_ids = [c["id"] for c in res_default["contacts"]]
    assert real_contact_id in default_ids
    assert seed_contact_id not in default_ids

    # search_data_lake with include_sample=True includes and orders real above sample
    res_with_sample = search_data_lake(client=mock_supabase, include_sample=True)
    contacts = res_with_sample["contacts"]
    assert len(contacts) == 2
    assert contacts[0]["id"] == real_contact_id
    assert contacts[0]["is_sample"] is False
    assert contacts[1]["id"] == seed_contact_id
    assert contacts[1]["is_sample"] is True

    # GET /v1/contacts default excludes sample contacts
    resp = client.get(
        "/v1/contacts",
        headers={"Authorization": "Bearer valid-token-recruiter"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(not item["is_sample"] for item in items)
    assert any(item["id"] == real_contact_id for item in items)
    assert not any(item["id"] == seed_contact_id for item in items)

    # GET /v1/contacts with include_sample=true includes and ranks real above sample
    resp_with = client.get(
        "/v1/contacts?include_sample=true",
        headers={"Authorization": "Bearer valid-token-recruiter"},
    )
    assert resp_with.status_code == 200
    items_with = resp_with.json()["items"]
    assert len(items_with) == 2
    assert items_with[0]["id"] == real_contact_id
    assert items_with[0]["is_sample"] is False
    assert items_with[1]["id"] == seed_contact_id
    assert items_with[1]["is_sample"] is True

    # 2. When DEMO_SHOW_SAMPLE is true:
    monkeypatch.setenv("DEMO_SHOW_SAMPLE", "true")
    res_env_true = search_data_lake(client=mock_supabase)
    assert len(res_env_true["contacts"]) == 2
    assert res_env_true["contacts"][0]["id"] == real_contact_id
    assert res_env_true["contacts"][1]["id"] == seed_contact_id

    # Passing include_sample=false still explicitly excludes sample
    res_explicit_false = search_data_lake(client=mock_supabase, include_sample=False)
    assert len(res_explicit_false["contacts"]) == 1
    assert res_explicit_false["contacts"][0]["id"] == real_contact_id


def test_extraction_precision_rules():
    """
    Precision rules:
    (a) Name and target company must appear in the same sentence or result block.
    (b) Title or surrounding text must mention recruiting, talent acquisition, campus/university hiring, or HR.
    """
    from app.search.extract_contacts import ExtractionResult, extract_contacts_from_text

    article_text = (
        "Rohit Verma leads university recruiting at Barclays India in their Mumbai campus. "
        "Amit Kumar is a Senior Software Engineer at Barclays India working on core banking infrastructure. "
        "Meanwhile, Priya Sharma leads campus talent acquisition at Google India."
    )

    # Mock LLM returning all 3 candidates initially
    mock_llm = MagicMock()
    mock_llm.generate_structured.return_value = ExtractionResult(
        contacts=[
            CandidateContact(
                name="Rohit Verma",
                title="Lead University Recruiter",
                company="Barclays India",
            ),
            CandidateContact(
                name="Amit Kumar",
                title="Senior Software Engineer",
                company="Barclays India",
            ),
            CandidateContact(
                name="Priya Sharma",
                title="Campus Talent Acquisition Lead",
                company="Google India",
            ),
        ]
    )

    # Target company is Barclays India
    extracted = extract_contacts_from_text(
        text=article_text,
        source_url="https://example.com/article",
        llm_provider=mock_llm,
        target_company="Barclays India",
    )

    names = [c.name for c in extracted]

    # 1. Valid recruiter at target company is kept
    assert "Rohit Verma" in names
    rohit = next(c for c in extracted if c.name == "Rohit Verma")
    assert "Barclays India" in rohit.matched_rule
    assert "Rohit Verma" in rohit.matched_rule

    # 2. Non-recruiter employee at Barclays India is dropped
    assert "Amit Kumar" not in names

    # 3. Person from another company (Google) in the same article is dropped
    assert "Priya Sharma" not in names
    assert len(extracted) == 1


def test_merged_seed_contact_survives_purge_and_user_saved_reference_counted(mock_supabase, test_user):
    """
    Verifies that:
    1. In purge dry-run, user_saved_contacts referencing contacts that would be deleted are counted.
    2. A seed contact matched and merged by a web result ends with source='web', is_sample=False,
       and SURVIVES purge_seed --yes, while pure seed rows are deleted.
    """
    comp_id = str(uuid.uuid4())
    mock_supabase.store["companies"].append({"id": comp_id, "name": "Barclays India", "category": "GCC"})

    # Seed contact 1: Priya Deshmukh (will be merged by web)
    priya_id = str(uuid.uuid4())
    mock_supabase.store["contacts"].append(
        {
            "id": priya_id,
            "name": "Priya Deshmukh",
            "title": "Junior Talent Sourcer",
            "company_id": comp_id,
            "linkedin_url": "https://linkedin.com/in/priyadeshmukh",
            "source": "seed",
        }
    )
    mock_supabase.store["contact_sources"].append({"id": str(uuid.uuid4()), "contact_id": priya_id, "source": "seed"})

    # Seed contact 2: Untouched Seed (pure seed, will NOT be merged)
    pure_seed_id = str(uuid.uuid4())
    mock_supabase.store["contacts"].append(
        {
            "id": pure_seed_id,
            "name": "Untouched Seed Contact",
            "title": "HR Lead",
            "company_id": comp_id,
            "source": "seed",
        }
    )
    mock_supabase.store["contact_sources"].append(
        {"id": str(uuid.uuid4()), "contact_id": pure_seed_id, "source": "seed"}
    )

    # User saves both seed contacts
    mock_supabase.store["user_saved_contacts"].append(
        {"id": str(uuid.uuid4()), "profile_id": str(test_user.id), "contact_id": priya_id}
    )
    mock_supabase.store["user_saved_contacts"].append(
        {"id": str(uuid.uuid4()), "profile_id": str(test_user.id), "contact_id": pure_seed_id}
    )

    # 1. Initial Purge Dry-Run: 2 seed contacts, 2 contact_sources, 2 referencing saved rows
    dry_run_res = run_purge(client=mock_supabase, confirm=False)
    assert dry_run_res["contacts_found"] == 2
    assert dry_run_res["sources_found"] == 2
    assert dry_run_res["user_saved_contacts_referenced"] == 2
    assert dry_run_res["contacts_deleted"] == 0

    # 2. Ingest web result that matches and merges Priya Deshmukh
    mock_search = MagicMock()
    mock_search.search.return_value = [
        SearchResult(
            title="Priya Deshmukh - Barclays LinkedIn",
            url="https://linkedin.com/in/priyadeshmukh",
            snippet="Priya Deshmukh is Lead Campus Recruiter at Barclays India in Mumbai.",
        )
    ]

    candidate_web = CandidateContact(
        name="Priya Deshmukh",
        title="Lead Campus Recruiter",
        company="Barclays India",
        linkedin_url="https://linkedin.com/in/priyadeshmukh",
        email="priya.deshmukh@barclays.example.com",
        source_url="https://linkedin.com/in/priyadeshmukh",
    )

    with patch(
        "app.search.ingest.extract_contacts_from_text",
        return_value=[candidate_web],
    ):
        stats = run_ingest(
            client=mock_supabase,
            category="GCC",
            limit=1,
            delay=0,
            dry_run=False,
            search_provider=mock_search,
            admin_user=test_user,
        )

    assert stats["contacts_merged"] == 1

    # Check Priya's updated state: source is 'web' and is_sample is False
    priya_row = next(c for c in mock_supabase.store["contacts"] if c["id"] == priya_id)
    assert priya_row["source"] == "web"
    assert priya_row["title"] == "Lead Campus Recruiter"

    lake_res = search_data_lake(client=mock_supabase, query="Priya", include_sample=True)
    priya_card = next(c for c in lake_res["contacts"] if c["id"] == priya_id)
    assert priya_card["is_sample"] is False

    # 3. Purge Dry-Run after merge: only 1 pure seed contact left to be purged
    dry_run_after = run_purge(client=mock_supabase, confirm=False)
    assert dry_run_after["contacts_found"] == 1
    assert dry_run_after["user_saved_contacts_referenced"] == 1

    # 4. Execute confirmed purge (purge_seed --yes)
    confirmed_purge = run_purge(client=mock_supabase, confirm=True)
    assert confirmed_purge["contacts_deleted"] == 1
    assert confirmed_purge["confirmed"] is True

    # Priya SURVIVED the purge because she is now source='web'!
    remaining_contacts = mock_supabase.store["contacts"]
    remaining_ids = [c["id"] for c in remaining_contacts]
    assert priya_id in remaining_ids
    assert pure_seed_id not in remaining_ids
