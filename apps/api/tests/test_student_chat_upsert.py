from unittest.mock import MagicMock, patch

from google.genai import types

from app.agent.tools import handle_upsert
from app.models.db import ProfileRole, UserProfile


def make_gemini_tool_call_response(tool_name: str, args: dict):
    fc = types.FunctionCall(name=tool_name, args=args)
    content = types.Content(role="model", parts=[types.Part(function_call=fc)])
    candidate = types.Candidate(content=content)
    return types.GenerateContentResponse(candidates=[candidate])


def make_gemini_text_response(text: str):
    content = types.Content(role="model", parts=[types.Part.from_text(text=text)])
    candidate = types.Candidate(content=content)
    return types.GenerateContentResponse(candidates=[candidate])


def test_upsert_child_tables_requires_student_record(mock_supabase):
    user = UserProfile(id="user-without-student", role=ProfileRole.STUDENT)
    res = handle_upsert(
        mock_supabase,
        user,
        "education",
        {"level": "bachelors", "degree": "BTech"},
    )
    assert res["error"] == "no_student_record"


def test_upsert_education_natural_key(mock_supabase):
    user = UserProfile(id="user-123", role=ProfileRole.STUDENT)
    # 1. Create student
    handle_upsert(
        mock_supabase,
        user,
        "students",
        {"full_name": "Riya Sharma", "batch_year": 2027},
    )

    # 2. Insert education
    res1 = handle_upsert(
        mock_supabase,
        user,
        "education",
        {
            "level": "twelfth",
            "score_value": 88.5,
            "score_scale": "percentage",
            "source": "user_said",
        },
    )
    assert res1["table"] == "education"
    assert res1["op"] == "created"

    # 3. Update education with same level
    res2 = handle_upsert(
        mock_supabase,
        user,
        "education",
        {
            "level": "twelfth",
            "score_value": 91.0,
            "score_scale": "percentage",
            "source": "user_said",
        },
    )
    assert res2["table"] == "education"
    assert res2["op"] == "updated"
    assert res2["id"] == res1["id"]


def test_upsert_internship_and_job(mock_supabase):
    user = UserProfile(id="user-123", role=ProfileRole.STUDENT)
    handle_upsert(
        mock_supabase,
        user,
        "students",
        {"full_name": "Riya Sharma", "batch_year": 2027},
    )

    # Upsert internship
    res_int = handle_upsert(
        mock_supabase,
        user,
        "internships",
        {
            "company": "TCS",
            "role": "Frontend Intern",
            "end_date": "2025-01-01",
            "source": "user_said",
        },
    )
    assert res_int["table"] == "internships"
    assert res_int["op"] == "created"

    # Verify score recomputed
    assert len(mock_supabase.store["score_events"]) > 0

    # Upsert job
    res_job = handle_upsert(
        mock_supabase,
        user,
        "jobs",
        {
            "company": "Infosys",
            "role": "Software Engineer",
            "start_date": "2024-01-01",
        },
    )
    assert res_job["table"] == "jobs"
    assert res_job["op"] == "created"


def test_student_chat_turn_with_injected_data(client, mock_supabase):
    # Setup initial student data
    mock_supabase.store["students"].append(
        {
            "id": "student-123",
            "profile_id": "user-123",
            "full_name": "Riya Sharma",
            "batch_year": 2027,
            "degree": "BSc CS",
            "college_id": None,
        }
    )

    mock_gemini = MagicMock()
    # Turn 1: tool call upsert internship
    t1 = make_gemini_tool_call_response(
        "upsert_record",
        {
            "table": "internships",
            "data": {
                "company": "TCS",
                "role": "Software Intern",
                "end_date": "2025-05-01",
            },
        },
    )
    t2 = make_gemini_text_response("Got it! I recorded your internship at TCS.")
    mock_gemini.models.generate_content.side_effect = [t1, t2]

    with patch("app.agent.runner.get_gemini_client", return_value=mock_gemini):
        response = client.post(
            "/v1/chat",
            headers={"Authorization": "Bearer valid-token-student"},
            json={"message": "I interned at TCS for 2 months ending in May 2025."},
        )

    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "TCS" in data["reply"]
    assert len(data["records_created"]) == 1
    assert data["records_created"][0]["table"] == "internships"
    assert data["records_created"][0]["op"] == "created"
