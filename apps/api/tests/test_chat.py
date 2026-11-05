from unittest.mock import MagicMock, patch
from google.genai import types
import pytest

from app.agent.runner import get_gemini_client
from app.models.api import AgentStepType


def make_gemini_tool_call_response(tool_name: str, args: dict):
    fc = types.FunctionCall(name=tool_name, args=args)
    content = types.Content(role="model", parts=[types.Part(function_call=fc)])
    candidate = types.Candidate(content=content)
    return types.GenerateContentResponse(candidates=[candidate])


def make_gemini_text_response(text: str):
    content = types.Content(role="model", parts=[types.Part.from_text(text=text)])
    candidate = types.Candidate(content=content)
    return types.GenerateContentResponse(candidates=[candidate])


def test_chat_direct_text_reply(client, mock_supabase):
    mock_gemini = MagicMock()
    mock_gemini.models.generate_content.return_value = make_gemini_text_response(
        "Hello Riya! How can I help with your campus recruiting profile today?"
    )

    with patch("app.agent.runner.get_gemini_client", return_value=mock_gemini):
        response = client.post(
            "/v1/chat",
            headers={"Authorization": "Bearer valid-token-student"},
            json={"message": "Hi, I want to create my student profile."},
        )

    assert response.status_code == 200
    data = response.json()
    assert "Hello Riya!" in data["reply"]
    assert len(data["steps"]) == 1
    assert data["steps"][0]["type"] == AgentStepType.FINAL_REPLY.value
    assert len(data["records_created"]) == 0

    # Verify raw_events contains user_message and agent_message
    events = mock_supabase.store["raw_events"]
    sources = [e["source"] for e in events]
    assert "user_message" in sources
    assert "agent_message" in sources

    # Verify agent_runs is completed
    runs = mock_supabase.store["agent_runs"]
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"
    assert runs[0]["profile_id"] == "user-123"


def test_chat_tool_use_upsert_student(client, mock_supabase):
    mock_gemini = MagicMock()
    # Turn 1: tool call to upsert_record for students
    # Turn 2: final textual reply
    turn_1 = make_gemini_tool_call_response(
        "upsert_record",
        {
            "table": "students",
            "data": {
                "full_name": "Riya Sharma",
                "batch_year": 2027,
                "degree": "BSc Computer Science",
            },
        },
    )
    turn_2 = make_gemini_text_response(
        "I've saved your student profile: Riya Sharma, batch 2027, BSc Computer Science!"
    )

    mock_gemini.models.generate_content.side_effect = [turn_1, turn_2]

    with patch("app.agent.runner.get_gemini_client", return_value=mock_gemini):
        response = client.post(
            "/v1/chat",
            headers={"Authorization": "Bearer valid-token-student"},
            json={"message": "I'm Riya Sharma, graduating batch 2027 doing BSc Computer Science."},
        )

    assert response.status_code == 200
    data = response.json()
    assert "saved your student profile" in data["reply"]
    assert len(data["records_created"]) == 1
    assert data["records_created"][0]["table"] == "students"
    assert data["records_created"][0]["op"] == "created"

    # Verify steps contain tool_call and final_reply
    step_types = [s["type"] for s in data["steps"]]
    assert AgentStepType.TOOL_CALL.value in step_types
    assert AgentStepType.FINAL_REPLY.value in step_types

    # Verify raw_events has all 4 event sources
    events = mock_supabase.store["raw_events"]
    sources = [e["source"] for e in events]
    assert "user_message" in sources
    assert "tool_call" in sources
    assert "tool_result" in sources
    assert "agent_message" in sources

    # Verify the student record was persisted in Supabase
    students = mock_supabase.store["students"]
    assert len(students) == 1
    assert students[0]["full_name"] == "Riya Sharma"
    assert students[0]["batch_year"] == 2027
    assert students[0]["profile_id"] == "user-123"

    # Verify agent_runs record is completed with steps
    runs = mock_supabase.store["agent_runs"]
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"
    assert len(runs[0]["steps"]) == 2


def test_chat_max_iterations_safety(client, mock_supabase):
    mock_gemini = MagicMock()
    # Always returns a tool call, never a final text reply
    repeated_tool_call = make_gemini_tool_call_response(
        "upsert_record",
        {
            "table": "students",
            "data": {"full_name": "Riya Sharma", "batch_year": 2027},
        },
    )
    mock_gemini.models.generate_content.return_value = repeated_tool_call

    with patch("app.agent.runner.get_gemini_client", return_value=mock_gemini):
        response = client.post(
            "/v1/chat",
            headers={"Authorization": "Bearer valid-token-student"},
            json={"message": "Loop test message"},
        )

    assert response.status_code == 200
    # Must terminate within max 5 iterations
    assert mock_gemini.models.generate_content.call_count == 5
    data = response.json()
    assert len(data["steps"]) >= 5
    runs = mock_supabase.store["agent_runs"]
    assert runs[0]["status"] == "completed"

