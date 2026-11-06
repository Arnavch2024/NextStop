import io
from unittest.mock import MagicMock, patch
import docx
from google.genai import types
import pypdf
import pytest

from app.models.api import AgentStepType


def create_sample_pdf_bytes(text: str = "Riya Sharma\nSt. Xavier's Mumbai\nBSc CS 2027") -> bytes:
    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    # Using pypdf annotations or simple writer
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


def create_sample_docx_bytes(text: str = "Riya Sharma - BSc CS 2027") -> bytes:
    doc = docx.Document()
    doc.add_paragraph(text)
    stream = io.BytesIO()
    doc.save(stream)
    return stream.getvalue()


def make_gemini_tool_call_response(tool_name: str, args: dict):
    fc = types.FunctionCall(name=tool_name, args=args)
    content = types.Content(role="model", parts=[types.Part(function_call=fc)])
    candidate = types.Candidate(content=content)
    return types.GenerateContentResponse(candidates=[candidate])


def make_gemini_text_response(text: str):
    content = types.Content(role="model", parts=[types.Part.from_text(text=text)])
    candidate = types.Candidate(content=content)
    return types.GenerateContentResponse(candidates=[candidate])


def test_upload_resume_invalid_mime_returns_415(client):
    response = client.post(
        "/v1/students/me/resume",
        headers={"Authorization": "Bearer valid-token-student"},
        files={"file": ("test.png", b"fake-png-data", "image/png")},
    )
    assert response.status_code == 415
    assert "Unsupported file type" in response.json()["detail"]


def test_upload_resume_too_large_returns_413(client):
    large_bytes = b"0" * (5 * 1024 * 1024 + 10)
    response = client.post(
        "/v1/students/me/resume",
        headers={"Authorization": "Bearer valid-token-student"},
        files={"file": ("resume.pdf", large_bytes, "application/pdf")},
    )
    assert response.status_code == 413
    assert "exceeds" in response.json()["detail"]


def test_upload_resume_success(client, mock_supabase):
    pdf_bytes = create_sample_pdf_bytes()

    mock_gemini = MagicMock()
    # Turn 1: tool call upsert education
    t1 = make_gemini_tool_call_response(
        "upsert_record",
        {
            "table": "education",
            "data": {
                "level": "bachelors",
                "score_value": 8.8,
                "score_scale": "cgpa10",
                "degree": "BSc CS",
            },
        },
    )
    # Turn 2: final reply
    t2 = make_gemini_text_response("Extracted education successfully.")
    mock_gemini.models.generate_content.side_effect = [t1, t2]

    with patch("app.agent.resume_parser.get_gemini_client", return_value=mock_gemini):
        response = client.post(
            "/v1/students/me/resume",
            headers={"Authorization": "Bearer valid-token-student"},
            files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
        )

    assert response.status_code == 200
    data = response.json()
    assert "document_id" in data
    assert "signed_url" in data
    assert "score" in data
    assert isinstance(data["records_created"], list)
    assert isinstance(data["missing_fields"], list)

    # Document was created in documents table
    doc_id = data["document_id"]
    docs = mock_supabase.store["documents"]
    assert any(d["id"] == doc_id for d in docs)

    # GET signed url endpoint
    get_res = client.get(
        f"/v1/students/me/resume/{doc_id}",
        headers={"Authorization": "Bearer valid-token-student"},
    )
    assert get_res.status_code == 200
    assert get_res.json()["document_id"] == doc_id
    assert "signed_url" in get_res.json()
