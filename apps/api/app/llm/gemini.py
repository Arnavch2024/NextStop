import json
import time
from typing import Any, List, Optional, Type, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.llm.base import (
    LLMError,
    LLMProvider,
    LLMResponse,
    MissingAPIKeyError,
    ToolCall,
)
from app.logger import logger

T = TypeVar("T", bound=BaseModel)


class GeminiLLMProvider(LLMProvider):
    """
    Google Gemini implementation of LLMProvider.
    Uses LLM_AGENT_MODEL for conversational tool-use and LLM_FAST_MODEL for extraction/drafting.
    Implements exponential backoff on 429 and 5xx errors.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        agent_model: Optional[str] = None,
        fast_model: Optional[str] = None,
        client: Optional[genai.Client] = None,
    ):
        self.api_key = api_key or settings.raw_gemini_api_key
        self.agent_model = agent_model or settings.LLM_AGENT_MODEL
        self.fast_model = fast_model or settings.LLM_FAST_MODEL
        self._client = client

    def _get_client(self) -> genai.Client:
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise MissingAPIKeyError(
                "Gemini API key is missing. Set GEMINI_API_KEY or GOOGLE_API_KEY in your environment."
            )
        self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _is_retryable_error(self, exc: Exception) -> bool:
        err_str = str(exc).lower()
        status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        if status_code in (429, 500, 502, 503, 504):
            return True
        return any(
            marker in err_str
            for marker in ("429", "rate limit", "quota", "resource_exhausted", "503", "unavailable", "500")
        )

    def _execute_with_retry(self, func, *args, **kwargs) -> Any:
        max_attempts = 3
        backoff_delay = 0.5
        for attempt in range(1, max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                if isinstance(exc, MissingAPIKeyError):
                    raise
                if self._is_retryable_error(exc) and attempt < max_attempts:
                    logger.warning(
                        f"Gemini API call failed with retryable error (attempt {attempt}/{max_attempts}): {exc}. "
                        f"Retrying in {backoff_delay}s..."
                    )
                    time.sleep(backoff_delay)
                    backoff_delay *= 2.0
                else:
                    raise exc

    def generate(
        self,
        messages: List[Any],
        tools: Optional[List[Any]] = None,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        client = self._get_client()
        target_model = model or self.agent_model

        config_kwargs: dict[str, Any] = {"temperature": temperature}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        if tools:
            config_kwargs["tools"] = tools

        config = types.GenerateContentConfig(**config_kwargs)

        def _call():
            return client.models.generate_content(
                model=target_model,
                contents=messages,
                config=config,
            )

        response = self._execute_with_retry(_call)

        text_content = None
        if hasattr(response, "text") and response.text:
            text_content = response.text

        tool_calls: List[ToolCall] = []
        raw_tool_calls = getattr(response, "function_calls", None)
        if raw_tool_calls:
            for fc in raw_tool_calls:
                tool_calls.append(ToolCall(name=fc.name, args=fc.args or {}))

        return LLMResponse(
            text=text_content,
            tool_calls=tool_calls,
        )

    def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
    ) -> T:
        client = self._get_client()
        target_model = model or self.fast_model

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_model,
            system_instruction=system_instruction,
            temperature=0.1,
        )

        last_error: Optional[Exception] = None
        current_prompt = prompt

        for attempt in (1, 2):
            try:

                def _call():
                    return client.models.generate_content(
                        model=target_model,
                        contents=current_prompt,
                        config=config,
                    )

                response = self._execute_with_retry(_call)
                raw_text = response.text or "{}"
                # Parse and validate with Pydantic
                parsed = response_model.model_validate_json(raw_text)
                return parsed
            except (ValidationError, json.JSONDecodeError, ValueError) as err:
                last_error = err
                logger.warning(f"generate_structured validation failed (attempt {attempt}/2): {err}. Retrying once...")
                current_prompt = (
                    f"{prompt}\n\nNote: Your previous output failed schema validation: {err}. "
                    f"Please produce strictly valid JSON matching the schema."
                )

        raise LLMError(f"Failed to generate structured JSON conforming to {response_model.__name__}: {last_error}")
