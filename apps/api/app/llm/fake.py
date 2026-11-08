from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from pydantic import BaseModel

from app.llm.base import LLMProvider, LLMResponse, ToolCall

T = TypeVar("T", bound=BaseModel)


class FakeLLMProvider(LLMProvider):
    """
    Test provider allowing deterministic injection of responses and tool calls.
    Used in tests to avoid live LLM calls and avoid mocking SDK internals.
    """

    def __init__(
        self,
        responses: Optional[List[Union[LLMResponse, str, Dict[str, Any]]]] = None,
        structured_responses: Optional[List[Any]] = None,
        generate_handler: Optional[Callable[..., LLMResponse]] = None,
    ):
        self.responses: List[LLMResponse] = []
        if responses:
            for r in responses:
                if isinstance(r, LLMResponse):
                    self.responses.append(r)
                elif isinstance(r, str):
                    self.responses.append(LLMResponse(text=r))
                elif isinstance(r, dict):
                    # Could be tool call dict {"tool": name, "args": {...}}
                    if "tool" in r or "name" in r:
                        name = r.get("name") or r.get("tool", "")
                        args = r.get("args") or r.get("input", {})
                        self.responses.append(LLMResponse(tool_calls=[ToolCall(name=name, args=args)]))
                    else:
                        self.responses.append(LLMResponse(text=str(r)))

        self.structured_responses: List[Any] = structured_responses or []
        self.generate_handler = generate_handler
        self.calls: List[Dict[str, Any]] = []

    def queue_response(self, response: Union[LLMResponse, str, ToolCall, List[ToolCall]]):
        if isinstance(response, LLMResponse):
            self.responses.append(response)
        elif isinstance(response, str):
            self.responses.append(LLMResponse(text=response))
        elif isinstance(response, ToolCall):
            self.responses.append(LLMResponse(tool_calls=[response]))
        elif isinstance(response, list) and all(isinstance(x, ToolCall) for x in response):
            self.responses.append(LLMResponse(tool_calls=response))

    def queue_structured(self, obj: Any):
        self.structured_responses.append(obj)

    def generate(
        self,
        messages: List[Any],
        tools: Optional[List[Any]] = None,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        self.calls.append(
            {
                "type": "generate",
                "messages": messages,
                "tools": tools,
                "system_instruction": system_instruction,
                "model": model,
            }
        )

        if self.generate_handler:
            return self.generate_handler(messages, tools, system_instruction, model, temperature)

        if self.responses:
            return self.responses.pop(0)

        return LLMResponse(text="Default fake LLM reply")

    def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
    ) -> T:
        self.calls.append(
            {
                "type": "generate_structured",
                "prompt": prompt,
                "response_model": response_model,
                "system_instruction": system_instruction,
                "model": model,
            }
        )

        if self.structured_responses:
            res = self.structured_responses.pop(0)
            if isinstance(res, response_model):
                return res
            if isinstance(res, dict):
                return response_model.model_validate(res)
            if isinstance(res, str):
                return response_model.model_validate_json(res)
            return res

        # Fallback to default instance
        return response_model.model_construct()
