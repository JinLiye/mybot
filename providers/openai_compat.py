"""Small OpenAI-compatible provider for mybot."""

from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from mybot.providers.base import LLMProvider, LLMResponse, ToolCallRequest


def parse_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
    if raw_arguments is None or raw_arguments == "":
        return {}
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if not isinstance(raw_arguments, str):
        return {"_invalid_tool_arguments": True, "error": "tool arguments must be a JSON object", "raw": str(raw_arguments)}
    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        return {
            "_invalid_tool_arguments": True,
            "error": f"invalid JSON tool arguments: {exc.msg} at char {exc.pos}",
            "raw": raw_arguments[:4000],
        }
    if not isinstance(parsed, dict):
        return {
            "_invalid_tool_arguments": True,
            "error": "tool arguments JSON must decode to an object",
            "raw": raw_arguments[:4000],
        }
    return parsed


class OpenAICompatProvider(LLMProvider):
    """Use a single OpenAI-compatible wire format for vLLM and Bailian."""

    def __init__(
        self,
        *,
        api_key: str,
        api_base: str,
        model: str,
    ) -> None:
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
        self._client = AsyncOpenAI(api_key=api_key, base_url=api_base)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        response = await self._client.chat.completions.create(**payload)
        choice = response.choices[0]
        message = choice.message
        tool_calls: list[ToolCallRequest] = []
        for tool_call in message.tool_calls or []:
            raw_arguments = tool_call.function.arguments or "{}"
            arguments = parse_tool_arguments(raw_arguments)
            tool_calls.append(
                ToolCallRequest(
                    id=tool_call.id,
                    name=tool_call.function.name,
                    arguments=arguments,
                )
            )

        usage: dict[str, int] = {}
        if response.usage is not None:
            usage = {
                "prompt_tokens": int(getattr(response.usage, "prompt_tokens", 0) or 0),
                "completion_tokens": int(getattr(response.usage, "completion_tokens", 0) or 0),
            }

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
        )

    def get_default_model(self) -> str:
        return self.model
