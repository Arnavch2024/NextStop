from unittest.mock import MagicMock
from app.logger import redact_secret_string


def test_missing_auth_header_returns_401(client):
    response = client.post("/v1/chat", json={"message": "Hello"})
    assert response.status_code == 401
    assert "Missing Authorization" in response.json()["detail"]


def test_invalid_token_returns_401(client):
    response = client.post(
        "/v1/chat",
        headers={"Authorization": "Bearer invalid-or-expired-token"},
        json={"message": "Hello"},
    )
    assert response.status_code == 401
    assert "Invalid or expired access token" in response.json()["detail"]


def test_redact_secrets_in_logs():
    raw = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secretpayload.signature"
    redacted = redact_secret_string(raw)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted
    assert "REDACTED" in redacted

    api_key_log = "api_key='AIzaSyAbc123456789xyz'"
    redacted_key = redact_secret_string(api_key_log)
    assert "AIzaSyAbc123456789xyz" not in redacted_key
    assert "REDACTED" in redacted_key

