import io

from app.config import settings


def test_student_records_template_endpoint(client):
    response = client.get("/v1/student-records/template")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "full_name,email,batch_year" in response.text


def test_student_records_import_and_list_officer(client, mock_supabase):
    csv_content = (
        "Name,Email,Batch,Branch,Degree,CGPA,Scale,Status,Rollno\n"
        "Riya Sharma,riya@college.edu,2027,Computer Engineering,BTech,8.9,cgpa10,in_college,CS-101\n"
        "Aarav Patel,aarav@college.edu,2028,Information Technology,BTech,8.5,cgpa10,in_college,IT-102\n"
        ",missing.name@college.edu,2027,Civil,BTech,7.5,cgpa10,in_college,CE-103\n"
        "Bad Year,bad@college.edu,2025,Mechanical,BTech,7.0,cgpa10,in_college,ME-104\n"
    )

    file_tuple = ("students.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")

    # Import with officer token
    res = client.post(
        "/v1/student-records",
        headers={"Authorization": "Bearer valid-token-officer"},
        files={"file": file_tuple},
    )
    assert res.status_code == 200
    report = res.json()
    assert report["imported"] == 2
    assert report["skipped"] == 2
    assert any("unmapped_column: Rollno" in r for r in report["reasons"])
    assert any("missing name" in r for r in report["reasons"])
    assert any("invalid batch_year" in r for r in report["reasons"])

    # List as officer
    list_res = client.get(
        "/v1/student-records",
        headers={"Authorization": "Bearer valid-token-officer"},
    )
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["total"] == 2
    assert data["status_counts"]["in_college"] == 2


def test_student_records_export_neutralizes_formulas(client, mock_supabase):
    # Add a row starting with formula trigger '='
    mock_supabase.store["student_records"].append(
        {
            "id": "sr-injection",
            "college_id": "col-mumbai-1",
            "full_name": "=cmd|' /C calc'!A0",
            "email": "+919999999999@test.com",
            "batch_year": 2027,
            "branch": "CS",
            "degree": "BTech",
            "score_value": 8.0,
            "score_scale": "cgpa10",
            "current_status": "in_college",
            "is_demo_data": False,
        }
    )

    res = client.get(
        "/v1/student-records/export",
        headers={"Authorization": "Bearer valid-token-officer"},
    )
    assert res.status_code == 200
    text = res.text
    # '=' must be sanitized to "'="
    assert "'=cmd|" in text
    assert "'+919999999999" in text


def test_batch_sharing_toggle_and_company_visibility(client, mock_supabase):
    college_id = "col-mumbai-1"
    # Seed a student record
    mock_supabase.store["student_records"].append(
        {
            "id": "sr-1",
            "college_id": college_id,
            "full_name": "Kavita Rao",
            "email": "kavita.secret@college.edu",
            "batch_year": 2027,
            "branch": "Computer Science",
            "degree": "BTech",
            "score_value": 9.2,
            "score_scale": "cgpa10",
            "current_status": "in_college",
            "opted_out": False,
            "is_demo_data": False,
        }
    )

    # 1. Company searches before batch is shared -> 0 results
    comp_res = client.get(
        "/v1/student-records",
        headers={"Authorization": "Bearer valid-token-company"},
    )
    assert comp_res.status_code == 200
    assert comp_res.json()["total"] == 0

    # 2. Officer shares batch 2027
    share_res = client.post(
        "/v1/colleges/me/batches/2027/share",
        headers={"Authorization": "Bearer valid-token-officer"},
        json={"shared": True},
    )
    assert share_res.status_code == 200
    assert share_res.json()["shared_with_recruiters"] is True

    # 3. Company & Recruiter search after batch shared -> returns Kavita Rao with minimal fields only (NO email, phone, aadhaar, documents)
    comp_res2 = client.get(
        "/v1/student-records",
        headers={"Authorization": "Bearer valid-token-company"},
    )
    assert comp_res2.status_code == 200
    items = comp_res2.json()["items"]
    assert len(items) == 1
    card = items[0]
    assert card["full_name"] == "Kavita Rao"
    assert "email" not in card  # Minimal fields: never contains personal details!
    assert "phone" not in card
    assert "aadhaar" not in card
    assert "documents" not in card
    assert "roll_number" not in card
    assert card["unverified"] is True

    # Recruiter also sees only minimal fields
    rec_res = client.get(
        "/v1/student-records",
        headers={"Authorization": "Bearer valid-token-recruiter"},
    )
    assert rec_res.status_code == 200
    rec_items = rec_res.json()["items"]
    assert len(rec_items) == 1
    assert "email" not in rec_items[0]
    assert "phone" not in rec_items[0]
    assert "aadhaar" not in rec_items[0]

    # 4. Student opts out -> disappears from company search
    client.patch(
        "/v1/student-records/sr-1/discoverability",
        headers={"Authorization": "Bearer valid-token-student"},
        json={"opted_out": True},
    )
    comp_res3 = client.get(
        "/v1/student-records",
        headers={"Authorization": "Bearer valid-token-company"},
    )
    assert comp_res3.json()["total"] == 0


def test_demo_auth_endpoints(client, monkeypatch):
    # 1. List demo accounts (public)
    res = client.get("/v1/auth/demo-accounts")
    assert res.status_code == 200
    accounts = res.json()
    assert len(accounts) >= 4
    roles = [a["role"] for a in accounts]
    assert "placement_officer" in roles
    assert "company" in roles
    assert "recruiter" in roles
    assert "student" in roles

    # 2. Demo login disabled by default -> 403
    monkeypatch.setattr(settings, "DEMO_LOGIN_ENABLED", False)
    res_disabled = client.post("/v1/auth/demo-login", json={"role": "placement_officer"})
    assert res_disabled.status_code == 403

    # 3. Demo login enabled -> 200 with access token
    monkeypatch.setattr(settings, "DEMO_LOGIN_ENABLED", True)
    res_enabled = client.post("/v1/auth/demo-login", json={"role": "placement_officer"})
    assert res_enabled.status_code == 200
    data = res_enabled.json()
    assert data["access_token"].startswith("demo-token-placement_officer")
    assert data["user"]["role"] == "placement_officer"
    assert data["user"]["is_demo"] is True
