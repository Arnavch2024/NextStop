from typing import Optional

from app.config import settings
from app.llm.base import (
    LLMError,
    LLMProvider,
    LLMResponse,
    MissingAPIKeyError,
    ToolCall,
)
from app.llm.fake import FakeLLMProvider
from app.llm.gemini import GeminiLLMProvider

_current_provider: Optional[LLMProvider] = None


def get_llm_provider(provider_name: Optional[str] = None) -> LLMProvider:
    """Returns the configured LLM provider instance."""
    global _current_provider
    if _current_provider is not None:
        return _current_provider

    name = provider_name or settings.LLM_PROVIDER.lower()
    if name == "gemini":
        return GeminiLLMProvider()
    elif name == "fake":
        return FakeLLMProvider()
    else:
        # Default fallback is Gemini
        return GeminiLLMProvider()


def set_llm_provider(provider: Optional[LLMProvider]) -> None:
    """Sets a global LLM provider override (e.g. FakeLLMProvider for testing)."""
    global _current_provider
    _current_provider = provider


__all__ = [
    "LLMProvider",
    "LLMResponse",
    "ToolCall",
    "LLMError",
    "MissingAPIKeyError",
    "GeminiLLMProvider",
    "FakeLLMProvider",
    "get_llm_provider",
    "set_llm_provider",
]
