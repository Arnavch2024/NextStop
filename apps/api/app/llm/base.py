from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)


class ToolCall(BaseModel):
    name: str
    args: Dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    text: Optional[str] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)


class LLMError(Exception):
    """Base exception for LLM provider errors."""

    pass


class MissingAPIKeyError(LLMError):
    """Raised when an API key is required but missing or invalid."""

    pass


class ModelRejectedError(LLMError):
    """Raised when a configured model is rejected by the LLM provider (e.g. 404/retired/unsupported)."""

    def __init__(self, model_name: str, message: str):
        self.model_name = model_name
        super().__init__(f"Configured model '{model_name}' was rejected by LLM provider: {message}")


class LLMProvider(ABC):
    """
    Provider-neutral interface for LLM interactions.
    Enables swapping providers (Gemini, Claude, OpenAI, Local) via env settings.
    """

    @abstractmethod
    def generate(
        self,
        messages: List[Any],
        tools: Optional[List[Any]] = None,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """
        Executes a turn with optional function calling.
        Returns provider-neutral LLMResponse containing text and/or tool_calls.
        """
        pass

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
    ) -> T:
        """
        Generates structured output conforming to response_model Pydantic schema.
        Employs native JSON/schema constraints where available and retries once
        on schema validation failure.
        """
        pass
