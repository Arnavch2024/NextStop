from app.models.db import ProfileRole, UserProfile
from app.routers.student_records import list_student_records
from scripts.purge_demo_data import purge_demo_data
from scripts.seed_demo_data import seed_demo_data


def test_demo_user_isolation(mock_supabase):
    """
    Demo safety rule test:
    - Demo users see ONLY is_demo_data = true records.
    - Non-demo users NEVER see demo records (is_demo_data = false only).
    """
    col_id = "col-mumbai-1"

    # Add 1 non-demo student record
    mock_supabase.store["student_records"].append(
        {
            "id": "sr-real-student",
            "college_id": col_id,
            "full_name": "Real Student",
            "email": "real.student@mumbai.edu",
            "batch_year": 2027,
            "branch": "Computer Engineering",
            "degree": "BTech",
            "score_value": 8.5,
            "score_scale": "cgpa10",
            "current_status": "in_college",
            "is_demo_data": False,
            "opted_out": False,
        }
    )

    # Add 1 demo student record
    mock_supabase.store["student_records"].append(
        {
            "id": "sr-demo-student",
            "college_id": col_id,
            "full_name": "Synthetic Candidate MU-01",
            "email": None,
            "batch_year": 2027,
            "branch": "Computer Engineering",
            "degree": "BTech",
            "score_value": 8.8,
            "score_scale": "cgpa10",
            "current_status": "in_college",
            "is_demo_data": True,
            "opted_out": False,
        }
    )

    # Enable batch sharing for 2027
    mock_supabase.store["batch_sharing"].append(
        {
            "id": "bs-2027",
            "college_id": col_id,
            "batch_year": 2027,
            "shared_with_recruiters": True,
        }
    )

    # 1. Demo Officer Query -> must only see sr-demo-student
    demo_officer = UserProfile(
        id="demo-officer-id",
        role=ProfileRole.PLACEMENT_OFFICER,
        display_name="Prof. Sunita Patil",
        college_id=col_id,
        is_demo=True,
    )
    officer_res = list_student_records(
        q=None,
        batch_year=None,
        status=None,
        branch=None,
        degree=None,
        college_id=None,
        min_score=None,
        page=1,
        page_size=20,
        user=demo_officer,
        client=mock_supabase,
    )
    assert officer_res.total == 1
    assert officer_res.items[0]["id"] == "sr-demo-student"
    assert officer_res.items[0]["is_demo_data"] is True

    # 2. Non-Demo Officer Query -> must only see sr-real-student
    real_officer = UserProfile(
        id="real-officer-id",
        role=ProfileRole.PLACEMENT_OFFICER,
        display_name="Prof. Real Officer",
        college_id=col_id,
        is_demo=False,
    )
    real_officer_res = list_student_records(
        q=None,
        batch_year=None,
        status=None,
        branch=None,
        degree=None,
        college_id=None,
        min_score=None,
        page=1,
        page_size=20,
        user=real_officer,
        client=mock_supabase,
    )
    assert real_officer_res.total == 1
    assert real_officer_res.items[0]["id"] == "sr-real-student"
    assert real_officer_res.items[0]["is_demo_data"] is False

    # 3. Demo Company Query -> must only see demo records
    demo_company = UserProfile(
        id="demo-company-id",
        role=ProfileRole.COMPANY,
        display_name="Pooja Sharma",
        company_id="comp-tcs-1",
        is_demo=True,
    )
    comp_res = list_student_records(
        q=None,
        batch_year=None,
        status=None,
        branch=None,
        degree=None,
        college_id=None,
        min_score=None,
        page=1,
        page_size=20,
        user=demo_company,
        client=mock_supabase,
    )
    assert comp_res.total == 1
    assert comp_res.items[0]["id"] == "sr-demo-student"

    # 4. Non-Demo Company Query -> must only see real records
    real_company = UserProfile(
        id="real-company-id",
        role=ProfileRole.COMPANY,
        display_name="Real Company",
        company_id="comp-real-1",
        is_demo=False,
    )
    real_comp_res = list_student_records(
        q=None,
        batch_year=None,
        status=None,
        branch=None,
        degree=None,
        college_id=None,
        min_score=None,
        page=1,
        page_size=20,
        user=real_company,
        client=mock_supabase,
    )
    assert real_comp_res.total == 1
    assert real_comp_res.items[0]["id"] == "sr-real-student"


def test_synthetic_names_carry_no_pii(mock_supabase):
    """
    Privacy guard test:
    Synthetic demo records must have NO email, NO phone, NO Aadhaar, and NO resume document.
    """
    mock_supabase.store["colleges"].extend(
        [
            {"id": "col-mumbai-1", "name": "University of Mumbai", "city": "Mumbai"},
            {"id": "col-jbims-1", "name": "Jamnalal Bajaj Institute of Management Studies (JBIMS)", "city": "Mumbai"},
            {"id": "col-vjti-1", "name": "Veermata Jijabai Technological Institute (VJTI)", "city": "Mumbai"},
            {"id": "col-iitb-1", "name": "IIT Bombay", "city": "Mumbai"},
        ]
    )
    mock_supabase.store["companies"].append(
        {"id": "comp-jpmc-1", "name": "JP Morgan Chase Global Technology", "category": "GCC"}
    )
    mock_supabase.store["students"].append(
        {"id": "st-demo-1", "profile_id": "demo-student-id", "college_id": "col-mumbai-1", "full_name": "Riya Sharma"}
    )

    # Seed demo data
    seed_demo_data(client=mock_supabase)

    demo_records = [r for r in mock_supabase.store["student_records"] if r.get("is_demo_data") is True]
    assert len(demo_records) >= 75  # ~60 at MU + ~15 at JBIMS

    for rec in demo_records:
        # PII checks
        assert rec.get("email") is None, f"Demo record {rec['id']} carries email!"
        assert "phone" not in rec or rec.get("phone") is None, f"Demo record {rec['id']} carries phone!"
        assert "aadhaar" not in rec or rec.get("aadhaar") is None, f"Demo record {rec['id']} carries Aadhaar!"
        assert rec.get("resume_ref") is None, f"Demo record {rec['id']} carries document reference!"
        # Visibly synthetic name
        name = rec.get("full_name", "")
        assert "Synthetic" in name or "Demo" in name, f"Demo record carries non-synthetic name: {name}"


def test_seed_demo_data_is_idempotent(mock_supabase):
    """
    Idempotency test:
    Running seed_demo_data multiple times produces identical row counts without duplication.
    """
    mock_supabase.store["colleges"].extend(
        [
            {"id": "col-mumbai-1", "name": "University of Mumbai", "city": "Mumbai"},
            {"id": "col-jbims-1", "name": "Jamnalal Bajaj Institute of Management Studies (JBIMS)", "city": "Mumbai"},
            {"id": "col-vjti-1", "name": "Veermata Jijabai Technological Institute (VJTI)", "city": "Mumbai"},
            {"id": "col-iitb-1", "name": "IIT Bombay", "city": "Mumbai"},
        ]
    )
    mock_supabase.store["companies"].append(
        {"id": "comp-jpmc-1", "name": "JP Morgan Chase Global Technology", "category": "GCC"}
    )
    mock_supabase.store["students"].append(
        {"id": "st-demo-1", "profile_id": "demo-student-id", "college_id": "col-mumbai-1", "full_name": "Riya Sharma"}
    )

    # First run
    run1 = seed_demo_data(client=mock_supabase)
    count1 = {
        k: len(mock_supabase.store[k])
        for k in ("student_records", "campus_hiring", "batch_sharing", "internships", "jobs", "contacts")
    }

    # Second run
    run2 = seed_demo_data(client=mock_supabase)
    count2 = {
        k: len(mock_supabase.store[k])
        for k in ("student_records", "campus_hiring", "batch_sharing", "internships", "jobs", "contacts")
    }

    assert count1 == count2
    assert run1["student_records"] == run2["student_records"]
    assert run1["campus_hiring"] == run2["campus_hiring"]


def test_purge_removes_only_demo_rows(mock_supabase):
    """
    Purge test:
    purge_demo_data --yes deletes ONLY rows flagged demo data, leaving non-demo rows untouched.
    """
    # 1. Setup colleges & non-demo data
    mock_supabase.store["colleges"].extend(
        [
            {"id": "col-mumbai-1", "name": "University of Mumbai", "city": "Mumbai"},
            {"id": "col-jbims-1", "name": "Jamnalal Bajaj Institute of Management Studies (JBIMS)", "city": "Mumbai"},
            {"id": "col-vjti-1", "name": "Veermata Jijabai Technological Institute (VJTI)", "city": "Mumbai"},
            {"id": "col-iitb-1", "name": "IIT Bombay", "city": "Mumbai"},
        ]
    )
    mock_supabase.store["companies"].append(
        {"id": "comp-jpmc-1", "name": "JP Morgan Chase Global Technology", "category": "GCC"}
    )
    mock_supabase.store["students"].append(
        {"id": "st-demo-1", "profile_id": "demo-student-id", "college_id": "col-mumbai-1", "full_name": "Riya Sharma"}
    )

    # Non-demo student record
    mock_supabase.store["student_records"].append(
        {
            "id": "real-sr-1",
            "college_id": "col-mumbai-1",
            "full_name": "Real Student Name",
            "email": "student@college.edu",
            "batch_year": 2027,
            "is_demo_data": False,
        }
    )

    # Non-demo contact
    mock_supabase.store["contacts"].append(
        {
            "id": "real-contact-1",
            "name": "Real Officer",
            "source": "manual",
            "role_type": "placement_officer",
        }
    )

    # Seed demo data
    seed_demo_data(client=mock_supabase)
    assert len(mock_supabase.store["student_records"]) == 76  # 75 demo + 1 real
    assert len(mock_supabase.store["contacts"]) == 4  # 3 demo + 1 real

    # Dry-run purge (confirm=False)
    preview = purge_demo_data(client=mock_supabase, confirm=False)
    assert preview["student_records"] == 75
    assert len(mock_supabase.store["student_records"]) == 76  # None deleted in dry run

    # Confirmed purge (confirm=True)
    deleted = purge_demo_data(client=mock_supabase, confirm=True)
    assert deleted["student_records"] == 75

    # Verify real rows remain untouched
    remaining_sr = mock_supabase.store["student_records"]
    assert len(remaining_sr) == 1
    assert remaining_sr[0]["id"] == "real-sr-1"
    assert remaining_sr[0]["is_demo_data"] is False

    remaining_contacts = mock_supabase.store["contacts"]
    assert len(remaining_contacts) == 1
    assert remaining_contacts[0]["id"] == "real-contact-1"
