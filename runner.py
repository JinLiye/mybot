"""LLM + tool execution loop for mybot."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from mybot.providers.base import LLMProvider
from mybot.tools.registry import ToolRegistry


@dataclass(slots=True)
class ToolEvent:
    name: str
    arguments: dict[str, Any]
    result_preview: str
    duration_ms: int
    error: str | None = None


@dataclass(slots=True)
class AgentRunResult:
    final_content: str
    messages: list[dict[str, Any]]
    tools_used: list[str] = field(default_factory=list)
    tool_events: list[ToolEvent] = field(default_factory=list)


def _preview(value: str, limit: int = 240) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


class AgentRunner:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    async def run(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: ToolRegistry,
        max_iterations: int,
        max_tokens: int,
        temperature: float,
    ) -> AgentRunResult:
        conversation = list(messages)
        tools_used: list[str] = []
        tool_events: list[ToolEvent] = []
        definitions = tools.get_definitions()

        for _ in range(max_iterations):
            response = await self.provider.chat(
                conversation,
                tools=definitions or None,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            if response.should_execute_tools:
                assistant_message: dict[str, Any] = {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                            },
                        }
                        for tc in response.tool_calls
                    ],
                }
                conversation.append(assistant_message)
                for tool_call in response.tool_calls:
                    tools_used.append(tool_call.name)
                    started_at = time.perf_counter()
                    error: str | None = None
                    try:
                        tool_result = await tools.execute(tool_call.name, tool_call.arguments)
                    except Exception as exc:
                        error = str(exc)
                        tool_result = f"Error executing {tool_call.name}: {error}"
                    duration_ms = int((time.perf_counter() - started_at) * 1000)
                    tool_events.append(
                        ToolEvent(
                            name=tool_call.name,
                            arguments=tool_call.arguments,
                            result_preview=_preview(tool_result),
                            duration_ms=duration_ms,
                            error=error,
                        )
                    )
                    conversation.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result,
                        }
                    )
                continue
            final_content = (response.content or "").strip()
            if not final_content:
                final_content = "[Empty model response]"
            conversation.append({"role": "assistant", "content": final_content})
            return AgentRunResult(
                final_content=final_content,
                messages=conversation,
                tools_used=tools_used,
                tool_events=tool_events,
            )

        raise RuntimeError("Agent runner exceeded max iterations")
