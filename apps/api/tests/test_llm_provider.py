from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from app.agent.runner import run_agent_loop
from app.llm import (
    FakeLLMProvider,
    GeminiLLMProvider,
    MissingAPIKeyError,
    ToolCall,
    set_llm_provider,
)
from app.models.api import AgentStepType
from app.models.db import ProfileRole, UserProfile


class SampleSchema(BaseModel):
    name: str
    score: int


def test_missing_api_key_error():
    provider = GeminiLLMProvider(api_key=None)
    # Explicitly ensure api_key is None
    provider.api_key = None
    with pytest.raises(MissingAPIKeyError) as exc_info:
        provider.generate(messages=["Hello"])
    assert "Gemini API key is missing" in str(exc_info.value)


def test_gemini_retry_on_429_backoff():
    mock_client = MagicMock()

    # Fail first call with 429, succeed on second
    class RateLimitError(Exception):
        status_code = 429

    success_resp = MagicMock()
    success_resp.text = "Success after rate limit"
    success_resp.function_calls = None

    mock_client.models.generate_content.side_effect = [
        RateLimitError("429 Resource exhausted: quota exceeded"),
        success_resp,
    ]

    provider = GeminiLLMProvider(api_key="test-key", client=mock_client)
    res = provider.generate(messages=["Test prompt"])

    assert res.text == "Success after rate limit"
    assert mock_client.models.generate_content.call_count == 2


def test_generate_structured_retry_on_validation_failure():
    mock_client = MagicMock()

    # Attempt 1 returns invalid json / missing fields, attempt 2 returns valid json
    bad_resp = MagicMock()
    bad_resp.text = '{"name": "Alice"}'  # missing required 'score'

    good_resp = MagicMock()
    good_resp.text = '{"name": "Alice", "score": 95}'

    mock_client.models.generate_content.side_effect = [bad_resp, good_resp]

    provider = GeminiLLMProvider(api_key="test-key", client=mock_client)
    result = provider.generate_structured(
        prompt="Extract student",
        response_model=SampleSchema,
    )

    assert result.name == "Alice"
    assert result.score == 95
    assert mock_client.models.generate_content.call_count == 2


def test_fake_llm_provider_swapped_across_whole_agent_loop(mock_supabase):
    fake_provider = FakeLLMProvider()

    # Turn 1: Return a tool call to upsert_record for colleges
    fake_provider.queue_response(
        ToolCall(
            name="upsert_record",
            args={"table": "colleges", "data": {"name": "VJTI Mumbai", "city": "Mumbai"}},
        )
    )
    # Turn 2: Return final reply
    fake_provider.queue_response("I have saved VJTI Mumbai to your profile records.")

    test_user = UserProfile(
        id="user-fake-123",
        role=ProfileRole.STUDENT,
        email="test@vjti.ac.in",
        display_name="Test Student",
    )

    set_llm_provider(fake_provider)
    try:
        chat_resp = run_agent_loop(
            user=test_user,
            message="I study at VJTI Mumbai.",
            supabase_client=mock_supabase,
            llm_provider=fake_provider,
        )

        assert "VJTI Mumbai" in chat_resp.reply
        assert len(chat_resp.records_created) == 1
        assert chat_resp.records_created[0].table == "colleges"
        assert chat_resp.records_created[0].op == "created"

        step_types = [s.type for s in chat_resp.steps]
        assert AgentStepType.TOOL_CALL in step_types
        assert AgentStepType.FINAL_REPLY in step_types

        # Verify college is in mock store
        colleges = mock_supabase.store["colleges"]
        assert any(c["name"] == "VJTI Mumbai" for c in colleges)
    finally:
        set_llm_provider(None)
