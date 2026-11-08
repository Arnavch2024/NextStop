import os
from unittest.mock import MagicMock, patch

import pytest

from app.llm.base import ModelRejectedError
from app.llm.check_models import (
    check_configured_models,
    check_model_cheap_call,
    should_skip_model_check,
)


def test_should_skip_in_test_or_ci():
    # In pytest, PYTEST_CURRENT_TEST is naturally present
    assert should_skip_model_check() is True

    # When CI is true
    with patch.dict(os.environ, {"CI": "true", "PYTEST_CURRENT_TEST": ""}):
        assert should_skip_model_check() is True

    # When SKIP_MODEL_CHECK is set
    with patch.dict(os.environ, {"SKIP_MODEL_CHECK": "true", "PYTEST_CURRENT_TEST": ""}):
        assert should_skip_model_check() is True


def test_check_configured_models_skips_in_test_env():
    results = check_configured_models()
    assert all("SKIPPED" in status for status in results.values())


def test_model_cheap_call_fails_loudly_on_rejection():
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("404 NOT_FOUND. models/gemini-1.5-flash is not found")

    with pytest.raises(ModelRejectedError) as exc_info:
        check_model_cheap_call("gemini-1.5-flash", client=mock_client)

    assert "gemini-1.5-flash" in str(exc_info.value)
    assert exc_info.value.model_name == "gemini-1.5-flash"
    assert "404 NOT_FOUND" in str(exc_info.value)


def test_check_configured_models_raises_model_rejected_error():
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("Model retired: gemini-old-model")

    # Temporarily bypass skip check to test runner behavior
    with patch("app.llm.check_models.should_skip_model_check", return_value=False):
        with pytest.raises(ModelRejectedError) as exc_info:
            check_configured_models(
                models=["gemini-old-model"],
                raise_on_error=True,
                client=mock_client,
            )

        assert "gemini-old-model" in str(exc_info.value)
        assert exc_info.value.model_name == "gemini-old-model"


def test_check_configured_models_success():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "pong"
    mock_client.models.generate_content.return_value = mock_resp

    with patch("app.llm.check_models.should_skip_model_check", return_value=False):
        results = check_configured_models(
            models=["gemini-3.5-flash", "gemini-3.5-flash-lite"],
            raise_on_error=True,
            client=mock_client,
        )

        assert results["gemini-3.5-flash"] == "OK"
        assert results["gemini-3.5-flash-lite"] == "OK"
        assert mock_client.models.generate_content.call_count == 2
