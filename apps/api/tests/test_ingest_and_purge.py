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


def test_merci_rodrigues_result_block_and_retained_drops():
    """
    Requirement 2:
    - Result-block fix: treat search result's title plus snippet as one block, including pipe- or dash-delimited titles.
    - Fixture test for Merci Rodrigues-style case (KEPT).
    - Person from another company in the same article is DROPPED.
    - Non-recruiter employee is DROPPED.
    """
    from app.search.extract_contacts import (
        CandidateContact,
        validate_recruiter_candidate,
    )

    # 1. Merci Rodrigues pipe-delimited search result
    merci_title = (
        "Merci Rodrigues Email & Phone Number | JPMorgan Chase & Co. Vice President - India Campus "
        "University Relations, Internships and Candidate Engagement Contact Information"
    )
    merci_snippet = "View Merci Rodrigues's email address and phone number for JPMorgan Chase & Co."
    cand_merci = CandidateContact(
        name="Merci Rodrigues",
        title="Vice President - India Campus University Relations, Internships and Candidate Engagement",
        company="JPMorgan Chase & Co.",
        source_url="https://rocketreach.co/merci-rodrigues-email_581408650",
    )

    val_res = validate_recruiter_candidate(
        candidate=cand_merci,
        text=f"{merci_title}\n{merci_snippet}",
        target_company="JPMorgan Chase",
    )
    assert val_res.is_valid is True
    assert "Merci Rodrigues" in val_res.matched_rule

    # 2. Person from another company in the same article is dropped
    cand_other_comp = CandidateContact(
        name="Sundar Pichai",
        title="Campus Talent Recruiter",
        company="Google",
    )
    multi_article = (
        "Merci Rodrigues leads campus university recruiting at JPMorgan Chase in Mumbai. "
        "Meanwhile, Sundar Pichai heads hiring at Google in Bengaluru."
    )
    val_other = validate_recruiter_candidate(
        candidate=cand_other_comp,
        text=multi_article,
        target_company="JPMorgan Chase",
    )
    assert val_other.is_valid is False
    assert "Rule (a) failed" in val_other.failed_rule

    # 3. Non-recruiter employee is dropped
    cand_engineer = CandidateContact(
        name="Rohan Joshi",
        title="Senior Software Engineer",
        company="JPMorgan Chase",
    )
    article_engineer = "Rohan Joshi is a Senior Software Engineer at JPMorgan Chase working on core payments."
    val_eng = validate_recruiter_candidate(
        candidate=cand_engineer,
        text=article_engineer,
        target_company="JPMorgan Chase",
    )
    assert val_eng.is_valid is False
    assert "Rule (b) failed" in val_eng.failed_rule


def test_confidence_capping_and_provenance_for_unverified_source(mock_supabase, test_user):
    """
    Requirement 3:
    - Candidate backed only by a single unverified/unfetched source gets confidence capped at 0.6 (never 1.0).
    - Source's published date and fetch status are stored.
    - Marked unverified in contact_sources.
    """
    from app.search.dedupe import upsert_contact

    candidate_headline = {
        "name": "Headline Recruiter",
        "title": "Lead Campus Talent Sourcer",
        "company_name": "Barclays India",
        "source_url": "https://example.com/unverified-headline",
        "confidence": 1.0,  # Proposed 1.0 by caller
        "fetch_status": "blocked",  # blocked by robots or HTTP 403
        "published_date": "2024-04-10",
        "verified": False,
    }

    res = upsert_contact(
        client=mock_supabase,
        candidate=candidate_headline,
        user=test_user,
        source="web",
    )

    contact_id = res["contact_id"]
    contact_row = next(c for c in mock_supabase.store["contacts"] if c["id"] == contact_id)
    # Confidence must be capped at 0.6, never 1.0!
    assert contact_row["confidence"] == 0.6

    source_row = next(s for s in mock_supabase.store["contact_sources"] if s["contact_id"] == contact_id)
    assert source_row["confidence"] == 0.6
    assert source_row["unverified"] is True
    assert source_row["fetch_status"] == "blocked"
    assert source_row["published_date"] == "2024-04-10"


def test_single_extraction_call_per_company_and_caching():
    """
    Requirement 4:
    - All company results extracted in ONE Gemini call.
    - Cache keyed by hash(model:company:prompt) avoids quota spend on re-run.
    """
    from app.search import cache
    from app.search.extract_contacts import CandidateContact, ExtractionResult, extract_company_contacts

    cache._MEMORY_EXTRACTION_CACHE.clear()
    if cache._EXTRACTION_CACHE_FILE.exists():
        try:
            cache._EXTRACTION_CACHE_FILE.unlink()
        except Exception:
            pass

    results = [
        {
            "url": "https://example.com/res1",
            "title": "Aarti Patil | Lead University Recruiter at Morgan Stanley Advantage Services",
            "snippet": "Aarti Patil manages campus hiring and university talent at Morgan Stanley Advantage Services in Mumbai.",
        },
        {
            "url": "https://example.com/res2",
            "title": "Morgan Stanley Advantage Services Careers",
            "snippet": "Join our technology and services teams in Mumbai.",
        },
    ]

    mock_llm = MagicMock()
    mock_llm.generate_structured.return_value = ExtractionResult(
        contacts=[
            CandidateContact(
                name="Aarti Patil",
                title="Lead University Recruiter",
                company="Morgan Stanley Advantage Services",
                source_url="https://example.com/res1",
            )
        ]
    )

    # First call: makes 1 LLM call and populates cache
    valid_contacts, dropped, was_cached = extract_company_contacts(
        results=results,
        target_company="Morgan Stanley Advantage Services",
        llm_provider=mock_llm,
    )
    assert len(valid_contacts) == 1
    assert was_cached is False
    assert mock_llm.generate_structured.call_count == 1

    # Second call with same inputs: served from cache, 0 new LLM calls!
    valid_cached, dropped_cached, was_cached_2 = extract_company_contacts(
        results=results,
        target_company="Morgan Stanley Advantage Services",
        llm_provider=mock_llm,
    )
    assert len(valid_cached) == 1
    assert was_cached_2 is True
    # Call count remains 1!
    assert mock_llm.generate_structured.call_count == 1


def test_data_broker_blocklist_rejects_aggregators_before_extraction():
    """
    Requirement 1:
    - Results from people-data aggregator domains (rocketreach.co, zoominfo.com, apollo.io, etc.)
      are rejected before extraction: never passed to LLM, never stored as source.
    - A broker result is rejected even if it matches rules (a) and (b).
    - A non-broker result is unaffected.
    """
    from app.search.extract_contacts import ExtractionResult, extract_company_contacts
    from app.search.providers.extract import is_data_broker

    # Domain checks
    assert is_data_broker("https://rocketreach.co/merci-rodrigues-email_581408650") is True
    assert is_data_broker("https://www.zoominfo.com/p/Jane-Doe/12345") is True
    assert is_data_broker("https://apollo.io/people/John/54321") is True
    assert is_data_broker("https://signalhire.com/candidates/123") is True
    assert is_data_broker("https://contactout.com/Jane-Doe") is True
    assert is_data_broker("https://lusha.com/contact/789") is True
    assert is_data_broker("https://barclays.com/careers") is False
    assert is_data_broker("https://hrtoday.in/vikas-sharma-appointed") is False

    broker_results = [
        {
            "url": "https://rocketreach.co/merci-rodrigues-email_581408650",
            "title": "Merci Rodrigues | JPMorgan Chase & Co. Vice President - India Campus University Relations",
            "snippet": "Contact info for Merci Rodrigues at JPMorgan Chase & Co.",
        },
        {
            "url": "https://jpmorgan.com/careers/india-campus",
            "title": "JPMorgan Chase & Co. Careers",
            "snippet": "Join our campus team in Mumbai.",
        },
    ]

    mock_llm = MagicMock()
    mock_llm.generate_structured.return_value = ExtractionResult(contacts=[])

    valid_contacts, dropped, was_cached = extract_company_contacts(
        results=broker_results,
        target_company="JPMorgan Chase",
        llm_provider=mock_llm,
    )

    # Check the prompt passed to LLM: rocketreach.co must NEVER be inside the prompt!
    assert mock_llm.generate_structured.call_count == 1
    call_args = mock_llm.generate_structured.call_args[1]
    prompt_text = call_args["prompt"]
    assert "rocketreach.co" not in prompt_text
    assert "jpmorgan.com/careers" in prompt_text


def test_dropped_candidates_not_persisted_anywhere(mock_supabase, test_user):
    """
    Requirement 3:
    - Confirm dropped candidates are not persisted anywhere (contacts, contact_sources, raw_events).
    - They appear only in the console report.
    """
    comp_id = str(uuid.uuid4())
    mock_supabase.store["companies"].append({"id": comp_id, "name": "Barclays India", "category": "GCC"})

    # Results with 1 valid recruiter and 2 dropped candidates
    results = [
        SearchResult(
            url="https://barclays.com/careers",
            title="Rohit Verma | University Recruiting Lead at Barclays India",
            snippet="Rohit Verma heads campus university hiring at Barclays India in Mumbai.",
        ),
        SearchResult(
            url="https://barclays.com/tech",
            title="Amit Kumar | Senior Software Engineer at Barclays India",
            snippet="Amit Kumar is Senior Software Engineer working on banking architecture at Barclays India.",
        ),
    ]

    mock_search = MagicMock()
    mock_search.search.return_value = results

    candidate_valid = CandidateContact(
        name="Rohit Verma",
        title="University Recruiting Lead",
        company="Barclays India",
        source_url="https://barclays.com/careers",
    )

    with patch(
        "app.search.ingest.extract_company_contacts",
        return_value=(
            [candidate_valid],
            [
                {
                    "name": "Amit Kumar",
                    "company": "Barclays India",
                    "extracted_title": "Senior Software Engineer",
                    "source_url": "https://barclays.com/tech",
                    "snippet": "Amit Kumar is Senior Software Engineer",
                    "rule_failed": "Rule (b) failed",
                }
            ],
            False,
        ),
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

    assert stats["contacts_added"] == 1
    assert stats["contacts_dropped"] == 1

    # Verify Amit Kumar is NOT in contacts table
    contact_names = [c.get("name") for c in mock_supabase.store["contacts"]]
    assert "Amit Kumar" not in contact_names
    assert "Rohit Verma" in contact_names

    # Verify Amit Kumar is NOT in contact_sources
    source_notes = [str(s) for s in mock_supabase.store["contact_sources"]]
    assert not any("Amit Kumar" in s for s in source_notes)

    # Verify Amit Kumar is NOT in raw_events
    raw_events = [str(r) for r in mock_supabase.store.get("raw_events", [])]
    assert not any("Amit Kumar" in r for r in raw_events)


def test_location_null_when_absent_in_source():
    """
    User Change 1:
    - location is null unless the source text states a location.
    - No default to the target city. Never infer.
    """
    from unittest.mock import MagicMock

    from app.search.extract_contacts import CandidateContact, extract_company_contacts

    # Result without any location mentioned
    results_no_loc = [
        {
            "url": "https://linkedin.com/in/recruiter1",
            "title": "Aarav Sharma - Campus Recruiter - Morgan Stanley | LinkedIn",
            "snippet": "Aarav Sharma is Campus Recruiter at Morgan Stanley early careers team.",
        }
    ]

    mock_llm = MagicMock()
    # LLM might attempt to guess Mumbai or leave it None
    mock_llm.generate_structured.return_value = MagicMock(
        contacts=[
            CandidateContact(
                name="Aarav Sharma",
                title="Campus Recruiter",
                company="Morgan Stanley",
                location="Mumbai",  # Hallucinated / inferred location not in text
                source_url="https://linkedin.com/in/recruiter1",
            )
        ]
    )

    valid_contacts, dropped, was_cached = extract_company_contacts(
        results=results_no_loc,
        target_company="Morgan Stanley",
        llm_provider=mock_llm,
    )

    assert len(valid_contacts) == 1
    # Because 'Mumbai' is NOT anywhere in the result text, it must be cleared to None!
    assert valid_contacts[0].location is None

    # Result with explicit location mentioned in text
    results_with_loc = [
        {
            "url": "https://linkedin.com/in/recruiter2",
            "title": "Riya Sen - Campus Recruiter - Morgan Stanley | LinkedIn",
            "snippet": "Riya Sen is Campus Recruiter at Morgan Stanley located in Mumbai.",
        }
    ]
    mock_llm.generate_structured.return_value = MagicMock(
        contacts=[
            CandidateContact(
                name="Riya Sen",
                title="Campus Recruiter",
                company="Morgan Stanley",
                location="Mumbai",
                source_url="https://linkedin.com/in/recruiter2",
            )
        ]
    )
    valid_contacts2, dropped2, was_cached2 = extract_company_contacts(
        results=results_with_loc,
        target_company="Morgan Stanley",
        llm_provider=mock_llm,
    )
    assert len(valid_contacts2) == 1
    assert valid_contacts2[0].location == "Mumbai"


def test_full_name_validation_rules():
    """
    Fix 2 & Plan Update 1:
    - Reject candidates whose surname is a bare initial (e.g. 'Maria F.', 'Gokul P.', 'Akshata T.').
    - Reject candidates that have only a single name token (e.g. 'Smriti', 'Cher').
    - Reject candidates whose surname is 1 or 2 uppercase letters (e.g. 'Rajiv MG', 'Ankit VK').
    - Accept valid full names (e.g. 'Priya Deshmukh', 'Savit Anand').
    """
    from app.search.extract_contacts import validate_full_name

    # Bare initials rejected
    ok, reason = validate_full_name("Maria F.")
    assert ok is False
    assert "bare initial" in reason

    ok, reason = validate_full_name("Gokul P.")
    assert ok is False
    assert "bare initial" in reason

    ok, reason = validate_full_name("Akshata T.")
    assert ok is False
    assert "bare initial" in reason

    ok, reason = validate_full_name("John D")
    assert ok is False
    assert "bare initial" in reason

    # Single-token names rejected
    ok, reason = validate_full_name("Smriti")
    assert ok is False
    assert "single token" in reason

    ok, reason = validate_full_name("Madonna")
    assert ok is False
    assert "single token" in reason

    # 1-2 uppercase letters surname rejected (e.g. Rajiv MG)
    ok, reason = validate_full_name("Rajiv MG")
    assert ok is False
    assert "uppercase letters" in reason

    ok, reason = validate_full_name("Ankit VK")
    assert ok is False
    assert "uppercase letters" in reason

    # Valid full names accepted
    ok, reason = validate_full_name("Priya Deshmukh")
    assert ok is True
    assert reason is None

    ok, reason = validate_full_name("Savit Anand")
    assert ok is True
    assert reason is None

    ok, reason = validate_full_name("Melville Pereira")
    assert ok is True
    assert reason is None


def test_location_multi_word_full_string_preserved(mock_supabase, test_user):
    """
    Fix 1:
    - Multi-word location like 'Pune Division' is preserved in full without truncation across
      candidate modeling and database storage.
    """
    from app.search.dedupe import upsert_contact

    comp_id = str(uuid.uuid4())
    mock_supabase.store["companies"].append({"id": comp_id, "name": "Barclays India", "category": "GCC"})

    candidate_data = {
        "name": "Anu Shree",
        "title": "Assistant Manager - Talent Acquisition",
        "company_id": comp_id,
        "location": "Pune Division, Maharashtra",
        "confidence": 0.6,
        "source_url": "https://example.com/anu",
        "fetch_status": "not_fetched",
        "stale": False,
    }

    res = upsert_contact(
        client=mock_supabase,
        candidate=candidate_data,
        user=test_user,
        source="web",
        source_url=candidate_data["source_url"],
    )

    contact_id = res["contact_id"]
    row = next(c for c in mock_supabase.store["contacts"] if c["id"] == contact_id)
    assert row["location"] == "Pune Division, Maharashtra"
    assert len(row["location"]) > 10


def test_no_snippet_text_stored_in_database(mock_supabase, test_user, caplog):
    """
    Fix 3 & Plan Update 4:
    - Raw snippet, highlight, or page text from search results must NOT be persisted anywhere durable:
      not in contacts, contact_sources, raw_events, or logs.
    - Captures log output during mocked ingest and asserts unique snippet string is absent.
    - Confirms .cache is gitignored.
    """
    import logging
    from pathlib import Path

    from app.search.extract_contacts import CandidateContact
    from app.search.ingest import run_ingest
    from app.search.providers.base import SearchProvider, SearchResult

    unique_snippet_marker = "SUPER_SECRET_SNIPPET_MARKER_987654321"

    comp_id = str(uuid.uuid4())
    mock_supabase.store["companies"].append({"id": comp_id, "name": "Barclays India", "category": "GCC"})

    class MockSearchSnippetProvider(SearchProvider):
        def search(self, query: str, num_results: int = 10):
            return [
                SearchResult(
                    url="https://linkedin.com/in/priya-snippet-test",
                    title="Priya Deshmukh - Campus Recruiter - Barclays India",
                    snippet=f"Priya is recruiter at Barclays India. {unique_snippet_marker}",
                    score=0.9,
                )
            ]

    candidate_valid = CandidateContact(
        name="Priya Deshmukh",
        title="Campus Recruiter",
        company="Barclays India",
        source_url="https://linkedin.com/in/priya-snippet-test",
    )

    with caplog.at_level(logging.DEBUG):
        with patch(
            "app.search.ingest.extract_company_contacts",
            return_value=([candidate_valid], [], False),
        ):
            run_ingest(
                client=mock_supabase,
                category="GCC",
                limit=1,
                delay=0,
                dry_run=False,
                search_provider=MockSearchSnippetProvider(),
                admin_user=test_user,
            )

    # 1. Assert absent from contacts table
    for contact in mock_supabase.store.get("contacts", []):
        contact_str = str(contact)
        assert unique_snippet_marker not in contact_str

    # 2. Assert absent from contact_sources table
    for source_entry in mock_supabase.store.get("contact_sources", []):
        source_str = str(source_entry)
        assert unique_snippet_marker not in source_str

    # 3. Assert absent from raw_events table
    for event in mock_supabase.store.get("raw_events", []):
        event_str = str(event)
        assert unique_snippet_marker not in event_str

    # 4. Assert absent from captured log output
    assert unique_snippet_marker not in caplog.text

    # 5. Confirm .cache is in .gitignore
    root_gitignore = Path(__file__).resolve().parent.parent.parent.parent / ".gitignore"
    api_gitignore = Path(__file__).resolve().parent.parent / ".gitignore"
    assert root_gitignore.exists()
    gitignore_text = root_gitignore.read_text(encoding="utf-8")
    assert ".cache" in gitignore_text
    if api_gitignore.exists():
        assert ".cache" in api_gitignore.read_text(encoding="utf-8")


def test_provider_budget_and_conditional_tavily_fallback(mock_supabase):
    """
    Fix 4:
    - Wide-run default queries per company = 2.
    - Run Tavily only when Exa returns fewer than N usable results (default 3) or fails.
    """
    from app.search.providers.base import SearchProvider, SearchResult
    from app.search.web import web_search_enrich

    class MockExaPlenty(SearchProvider):
        def search(self, query: str, num_results: int = 10):
            return [
                SearchResult(
                    url=f"https://linkedin.com/in/recruiter-{i}",
                    title=f"Recruiter {i} - Barclays",
                    snippet="Campus hiring",
                )
                for i in range(4)
            ]

    class MockTavilySpy(SearchProvider):
        def __init__(self):
            self.called = False

        def search(self, query: str, num_results: int = 10):
            self.called = True
            return []

    tavily_spy = MockTavilySpy()
    # Case 1: Exa returns 4 usable results (>= 3). Tavily must NOT be called.
    enrich_res = web_search_enrich(
        client=mock_supabase,
        query="campus recruiter Barclays",
        multi_provider=True,
        providers=[MockExaPlenty(), tavily_spy],
        options_version="test_budget_plenty",
    )
    assert tavily_spy.called is False
    assert len(enrich_res["results"]) == 4

    # Case 2: Exa returns 1 usable result (< 3). Tavily MUST be called.
    class MockExaSparse(SearchProvider):
        def search(self, query: str, num_results: int = 10):
            return [
                SearchResult(url="https://linkedin.com/in/only-one", title="Only One - Barclays", snippet="Recruiting")
            ]

    tavily_spy2 = MockTavilySpy()
    web_search_enrich(
        client=mock_supabase,
        query="campus recruiter Barclays",
        multi_provider=True,
        providers=[MockExaSparse(), tavily_spy2],
        options_version="test_budget_sparse",
    )
    assert tavily_spy2.called is True


def test_call_estimate_exceeds_200_requires_yes(mock_supabase):
    """
    Fix 4:
    - When estimated search calls exceeds 200, require confirm_yes=True / --yes.
    """
    import pytest

    from app.search.ingest import run_ingest

    # 101 companies x 2 queries x 2 search providers = 404 search calls (> 200)
    fake_companies = [{"id": f"comp-{i}", "name": f"Company {i}", "category": "GCC"} for i in range(101)]
    mock_supabase.store["companies"] = fake_companies

    # Without confirm_yes -> raises ValueError
    with pytest.raises(ValueError, match="exceeds budget of 200"):
        run_ingest(client=mock_supabase, category="GCC", confirm_yes=False)

    # With confirm_yes=True -> does not raise budget error
    mock_search = MagicMock()
    mock_search.search.return_value = []
    stats = run_ingest(
        client=mock_supabase,
        category="GCC",
        limit=101,
        confirm_yes=True,
        search_provider=mock_search,
    )
    assert stats["companies_processed"] == 101


def test_only_urls_filter_option(mock_supabase, test_user):
    """
    Fix 6:
    - --only-urls writes/accepts only candidates whose source_url is in the approved list.
    """
    from app.search.extract_contacts import CandidateContact
    from app.search.ingest import run_ingest
    from app.search.providers.base import SearchResult

    comp_id = str(uuid.uuid4())
    mock_supabase.store["companies"].append({"id": comp_id, "name": "Barclays India", "category": "GCC"})

    approved_url = "https://linkedin.com/in/approved-recruiter"
    unapproved_url = "https://linkedin.com/in/unapproved-recruiter"

    cands = [
        CandidateContact(
            name="Approved Recruiter",
            title="Campus Recruiter",
            company="Barclays India",
            source_url=approved_url,
        ),
        CandidateContact(
            name="Unapproved Recruiter",
            title="Campus Recruiter",
            company="Barclays India",
            source_url=unapproved_url,
        ),
    ]

    mock_search = MagicMock()
    mock_search.search.return_value = [
        SearchResult(url=approved_url, title="Approved Recruiter - Barclays", snippet="Recruiting"),
        SearchResult(url=unapproved_url, title="Unapproved Recruiter - Barclays", snippet="Recruiting"),
    ]

    with patch("app.search.ingest.extract_company_contacts", return_value=(cands, [], False)):
        stats = run_ingest(
            client=mock_supabase,
            category="GCC",
            limit=1,
            delay=0,
            dry_run=False,
            search_provider=mock_search,
            admin_user=test_user,
            only_urls=approved_url,  # Restrict to only the approved URL
        )

    # Only the approved candidate should be added!
    assert stats["contacts_added"] == 1
    stored_names = [c["name"] for c in mock_supabase.store["contacts"]]
    assert "Approved Recruiter" in stored_names
    assert "Unapproved Recruiter" not in stored_names


def test_staleness_calculation_and_confidence_capping():
    """
    User Change 2:
    - stale=true when source_published_date is older than 12 months.
    - stale=null when the date is missing (unknown, not fresh).
    - stale=false when <= 12 months.
    - For candidates backed only by a single unfetched source, cap confidence at 0.4 when stale and 0.6 otherwise.
    """
    from datetime import datetime, timezone
    from unittest.mock import MagicMock

    from app.search.extract_contacts import CandidateContact, extract_company_contacts
    from app.search.providers.extract import compute_staleness

    fixed_now = datetime(2026, 6, 1, tzinfo=timezone.utc)

    # 1. Date missing -> None
    assert compute_staleness(None, now=fixed_now) is None
    assert compute_staleness("", now=fixed_now) is None

    # 2. Older than 12 months (> 365 days) -> True
    assert compute_staleness("2024-05-01", now=fixed_now) is True
    assert compute_staleness("2025-01-15T00:00:00Z", now=fixed_now) is True

    # 3. Within 12 months (<= 365 days) -> False
    assert compute_staleness("2026-01-10", now=fixed_now) is False
    assert compute_staleness("2025-10-01", now=fixed_now) is False

    # 4. Confidence capping check via extract_company_contacts
    mock_llm = MagicMock()
    mock_llm.generate_structured.return_value = MagicMock(
        contacts=[
            CandidateContact(
                name="Old Recruiter",
                title="Campus Recruiter",
                company="Barclays",
                confidence=1.0,
                source_url="https://barclays.com/old",
            ),
            CandidateContact(
                name="Fresh Recruiter",
                title="Campus Recruiter",
                company="Barclays",
                confidence=1.0,
                source_url="https://barclays.com/new",
            ),
            CandidateContact(
                name="Undated Recruiter",
                title="Campus Recruiter",
                company="Barclays",
                confidence=1.0,
                source_url="https://barclays.com/undated",
            ),
        ]
    )

    test_results = [
        {
            "url": "https://barclays.com/old",
            "title": "Old Recruiter - Campus Recruiter - Barclays",
            "snippet": "Campus hiring at Barclays.",
            "published_date": "2023-01-01",  # Stale (>12mo)
            "fetch_status": "not_fetched",
        },
        {
            "url": "https://barclays.com/new",
            "title": "Fresh Recruiter - Campus Recruiter - Barclays",
            "snippet": "Campus hiring at Barclays.",
            "published_date": "2026-05-01",  # Fresh (<=12mo)
            "fetch_status": "not_fetched",
        },
        {
            "url": "https://barclays.com/undated",
            "title": "Undated Recruiter - Campus Recruiter - Barclays",
            "snippet": "Campus hiring at Barclays.",
            "published_date": None,  # Undated
            "fetch_status": "not_fetched",
        },
    ]

    valid_cands, dropped, was_cached = extract_company_contacts(
        results=test_results,
        target_company="Barclays",
        llm_provider=mock_llm,
    )

    by_name = {c.name: c for c in valid_cands}

    # Old recruiter: stale is True -> confidence capped at 0.4
    assert by_name["Old Recruiter"].stale is True
    assert by_name["Old Recruiter"].confidence == 0.4

    # Fresh recruiter: stale is False -> confidence capped at 0.6
    assert by_name["Fresh Recruiter"].stale is False
    assert by_name["Fresh Recruiter"].confidence == 0.6

    # Undated recruiter: stale is None -> confidence capped at 0.6
    assert by_name["Undated Recruiter"].stale is None
    assert by_name["Undated Recruiter"].confidence == 0.6


def test_cache_key_changes_with_provider_options():
    """
    User Change 3:
    - Search cache key must include a provider-options version.
    """
    from app.search.cache import compute_query_hash

    query = "campus recruiter Barclays Mumbai"
    purpose = "campus recruiter at Barclays, Mumbai"

    hash_v1 = compute_query_hash(query, purpose, options_version="v1_plain")
    hash_v2 = compute_query_hash(query, purpose, options_version="v2_exa_highlights")
    hash_default = compute_query_hash(query, purpose)

    assert hash_v1 != hash_v2
    assert hash_default == hash_v2


def test_ranking_order_mumbai_and_fresh(mock_supabase):
    """
    User Change 2 & 5:
    - Expose stale, source_published_date and location through the API/schema.
    - Rank Mumbai-stated and fresh contacts above others without excluding any.
    - Rank real (non-seed) contacts above sample ones.
    """
    comp_id = str(uuid.uuid4())
    mock_supabase.store["companies"].append({"id": comp_id, "name": "Morgan Stanley", "category": "GCC"})

    # Create 4 contacts with different locations, staleness, and seed states
    contacts_data = [
        {
            "id": str(uuid.uuid4()),
            "name": "Seed Recruiter",
            "company_id": comp_id,
            "title": "Campus Recruiter",
            "location": "Mumbai",
            "stale": False,
            "source": "seed",
            "confidence": 1.0,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Real Stale Outside",
            "company_id": comp_id,
            "title": "Campus Recruiter",
            "location": "Bengaluru",
            "stale": True,
            "source": "web",
            "confidence": 0.4,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Real Fresh Mumbai",
            "company_id": comp_id,
            "title": "Campus Recruiter",
            "location": "Mumbai",
            "stale": False,
            "source": "web",
            "confidence": 0.6,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Real Undated Mumbai",
            "company_id": comp_id,
            "title": "Campus Recruiter",
            "location": "Mumbai",
            "stale": None,
            "source": "web",
            "confidence": 0.6,
        },
    ]

    for c in contacts_data:
        mock_supabase.store["contacts"].append(c)

    res = search_data_lake(client=mock_supabase, query="Morgan Stanley", include_sample=True)
    ordered_names = [c["name"] for c in res["contacts"]]

    # Expected order:
    # 1. Real Fresh Mumbai (real=0, mumbai=0, fresh=0)
    # 2. Real Undated Mumbai (real=0, mumbai=0, undated=1)
    # 3. Real Stale Outside (real=0, outside=1, stale=2)
    # 4. Seed Recruiter (seed=1)
    assert ordered_names == [
        "Real Fresh Mumbai",
        "Real Undated Mumbai",
        "Real Stale Outside",
        "Seed Recruiter",
    ]


def test_tavily_style_linkedin_result_with_title_accepted():
    """
    Scenario 1:
    - Tavily-style LinkedIn result with title 'Name - Campus Recruiter - Company | LinkedIn' is accepted.
    """
    from app.search.extract_contacts import CandidateContact, validate_recruiter_candidate

    title = "Merci Rodrigues - Campus Recruiter - Barclays | LinkedIn"
    snippet = "Early careers talent acquisition for campus recruiting in India."
    cand = CandidateContact(
        name="Merci Rodrigues",
        title="Campus Recruiter",
        company="Barclays",
        source_url="https://linkedin.com/in/merci-rodrigues",
    )

    val_res = validate_recruiter_candidate(
        candidate=cand,
        text=f"{title}\n{snippet}",
        target_company="Barclays",
    )
    assert val_res.is_valid is True
    assert "Barclays" in val_res.matched_rule


def test_name_only_empty_snippet_never_reaches_llm():
    """
    Scenario 5:
    - Pre-filter: drop any result whose snippet/text is empty AND whose title is only a person's name.
    - Never sent to Gemini; counted as 'skipped, no information'.
    """
    from unittest.mock import MagicMock

    from app.search.extract_contacts import extract_company_contacts
    from app.search.providers.extract import is_name_only_empty_snippet

    assert is_name_only_empty_snippet("John Doe | LinkedIn", snippet="", page_text=None) is True
    assert is_name_only_empty_snippet("John Doe - Campus Recruiter - Barclays | LinkedIn", snippet="") is False
    assert is_name_only_empty_snippet("John Doe", snippet="Recruiter at Barclays") is False

    mock_llm = MagicMock()

    results = [
        {
            "url": "https://linkedin.com/in/johndoe",
            "title": "John Doe | LinkedIn",
            "snippet": "",
        }
    ]

    ext_res = extract_company_contacts(
        results=results,
        target_company="Barclays",
        llm_provider=mock_llm,
    )

    valid_cands, dropped, was_cached = ext_res
    # Pre-filtered: never sent to LLM!
    assert mock_llm.generate_structured.call_count == 0
    assert len(valid_cands) == 0
    assert ext_res.skipped_no_info == 1


def test_multi_provider_merge_and_dedupe(mock_supabase):
    """
    Scenario 6:
    - Exa AND Tavily search results merged and deduplicated by URL, keeping richer snippet.
    """
    from app.search.providers.base import SearchProvider, SearchResult
    from app.search.web import web_search_enrich

    class MockExa(SearchProvider):
        def search(self, query: str, num_results: int = 10):
            return [
                SearchResult(
                    url="https://linkedin.com/in/priya-deshmukh/",
                    title="Priya Deshmukh - Campus Recruiter - Barclays",
                    snippet="Short snippet",
                    score=0.9,
                )
            ]

    class MockTavily(SearchProvider):
        def search(self, query: str, num_results: int = 10):
            return [
                SearchResult(
                    url="https://linkedin.com/in/priya-deshmukh",  # Duplicate URL (without trailing slash)
                    title="Priya Deshmukh - Campus Recruiter - Barclays | LinkedIn",
                    snippet="Much longer richer snippet mentioning early careers and campus hiring at Barclays in Mumbai",
                    score=0.85,
                    published_date="2026-03-01",
                )
            ]

    enrich_res = web_search_enrich(
        client=mock_supabase,
        query="campus recruiter Barclays",
        multi_provider=True,
        providers=[MockExa(), MockTavily()],
        options_version="test_options",
    )

    results = enrich_res["results"]
    assert len(results) == 1
    # Kept the richer snippet from Tavily
    assert "Much longer richer snippet" in results[0]["snippet"]
    assert results[0]["published_date"] == "2026-03-01"
