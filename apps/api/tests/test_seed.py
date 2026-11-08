from app.db.seed import seed_data


def test_seed_idempotency(mock_supabase):
    # First seed run
    summary1 = seed_data(mock_supabase)
    assert summary1["colleges"] >= 40
    assert summary1["companies"] >= 30
    assert summary1["contacts"] >= 25

    colleges_count_1 = len(mock_supabase.store["colleges"])
    companies_count_1 = len(mock_supabase.store["companies"])
    contacts_count_1 = len(mock_supabase.store["contacts"])
    sources_count_1 = len(mock_supabase.store["contact_sources"])

    # Second seed run (must be completely idempotent - no duplicates)
    summary2 = seed_data(mock_supabase)
    assert summary2 == summary1

    assert len(mock_supabase.store["colleges"]) == colleges_count_1
    assert len(mock_supabase.store["companies"]) == companies_count_1
    assert len(mock_supabase.store["contacts"]) == contacts_count_1
    assert len(mock_supabase.store["contact_sources"]) == sources_count_1


def test_seed_data_properties(mock_supabase):
    seed_data(mock_supabase)

    # 1. Colleges: all in Mumbai
    colleges = mock_supabase.store["colleges"]
    assert len(colleges) >= 40
    for col in colleges:
        assert col["city"].lower() == "mumbai"

    # 2. Companies: GCC, startup, enterprise categories present
    companies = mock_supabase.store["companies"]
    assert len(companies) >= 30
    categories = {c.get("category") for c in companies}
    assert "GCC" in categories
    assert "enterprise" in categories
    assert "startup" in categories

    # 3. Contacts: source='seed', role_type in expected types, no phone numbers in lake
    contacts = mock_supabase.store["contacts"]
    assert len(contacts) >= 25
    for contact in contacts:
        assert contact["source"] == "seed"
        assert contact.get("phone") is None
        assert contact["role_type"] in ("campus_recruiter", "placement_officer", "hr", "other", "recruiter")

    # 4. Provenance: synthetic note attached
    sources = mock_supabase.store["contact_sources"]
    assert len(sources) >= 25
    for src in sources:
        assert src["source"] == "seed"
        assert src["note"] == "synthetic"
        assert src["unverified"] is False
