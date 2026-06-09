"""LLM + tool execution loop for mybot."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

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
    trace: dict[str, Any] = field(default_factory=dict)


def _now_iso() -> str:
    return datetime.now().isoformat()


def _preview(value: str, limit: int = 240) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def _usage_with_total(usage: dict[str, int]) -> dict[str, int]:
    normalized = dict(usage)
    if normalized and "total_tokens" not in normalized:
        normalized["total_tokens"] = int(normalized.get("prompt_tokens", 0)) + int(
            normalized.get("completion_tokens", 0)
        )
    return normalized


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
        tools_enabled: bool = True,
    ) -> AgentRunResult:
        conversation = list(messages)
        tools_used: list[str] = []
        tool_events: list[ToolEvent] = []
        definitions = tools.get_definitions() if tools_enabled else []
        run_started = time.perf_counter()
        trace: dict[str, Any] = {
            "run_id": str(uuid4()),
            "status": "running",
            "started_at": _now_iso(),
            "ended_at": None,
            "duration_ms": None,
            "steps": [],
        }
        steps: list[dict[str, Any]] = trace["steps"]

        for iteration in range(1, max_iterations + 1):
            llm_started = time.perf_counter()
            steps.append(
                {
                    "type": "llm_request",
                    "iteration": iteration,
                    "timestamp": _now_iso(),
                    "message_count": len(conversation),
                    "tools_enabled": tools_enabled,
                    "tool_count": len(definitions),
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
            )
            response = await self.provider.chat(
                conversation,
                tools=definitions or None,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            llm_duration_ms = int((time.perf_counter() - llm_started) * 1000)
            response_tool_calls = [
                {
                    "id": tool_call.id,
                    "name": tool_call.name,
                    "arguments": tool_call.arguments,
                }
                for tool_call in response.tool_calls
            ]
            steps.append(
                {
                    "type": "llm_response",
                    "iteration": iteration,
                    "timestamp": _now_iso(),
                    "duration_ms": llm_duration_ms,
                    "finish_reason": response.finish_reason,
                    "usage": _usage_with_total(response.usage),
                    "content_preview": _preview(response.content or ""),
                    "tool_calls": response_tool_calls,
                }
            )
            if tools_enabled and response.should_execute_tools:
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
                    steps.append(
                        {
                            "type": "tool_call",
                            "iteration": iteration,
                            "timestamp": _now_iso(),
                            "tool_call_id": tool_call.id,
                            "name": tool_call.name,
                            "arguments": tool_call.arguments,
                        }
                    )
                    started_at = time.perf_counter()
                    error: str | None = None
                    try:
                        tool_result = await tools.execute(tool_call.name, tool_call.arguments)
                    except Exception as exc:
                        error = str(exc)
                        tool_result = f"Error executing {tool_call.name}: {error}"
                    duration_ms = int((time.perf_counter() - started_at) * 1000)
                    result_preview = _preview(tool_result)
                    tool_events.append(
                        ToolEvent(
                            name=tool_call.name,
                            arguments=tool_call.arguments,
                            result_preview=result_preview,
                            duration_ms=duration_ms,
                            error=error,
                        )
                    )
                    steps.append(
                        {
                            "type": "tool_result",
                            "iteration": iteration,
                            "timestamp": _now_iso(),
                            "tool_call_id": tool_call.id,
                            "name": tool_call.name,
                            "duration_ms": duration_ms,
                            "error": error,
                            "result": tool_result,
                            "result_preview": result_preview,
                        }
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
            steps.append(
                {
                    "type": "final",
                    "iteration": iteration,
                    "timestamp": _now_iso(),
                    "content_preview": _preview(final_content),
                }
            )
            trace["status"] = "completed"
            trace["ended_at"] = _now_iso()
            trace["duration_ms"] = int((time.perf_counter() - run_started) * 1000)
            return AgentRunResult(
                final_content=final_content,
                messages=conversation,
                tools_used=tools_used,
                tool_events=tool_events,
                trace=trace,
            )

        final_content = (
            f"[Agent stopped after reaching max_iterations={max_iterations}. "
            "The task may be partially complete. Use /trace to inspect the tool chain, "
            "or retry with MYBOT_MAX_ITERATIONS set higher.]"
        )
        trace["status"] = "error"
        trace["ended_at"] = _now_iso()
        trace["duration_ms"] = int((time.perf_counter() - run_started) * 1000)
        steps.append(
            {
                "type": "error",
                "timestamp": _now_iso(),
                "message": "Agent runner exceeded max iterations",
            }
        )
        conversation.append({"role": "assistant", "content": final_content})
        return AgentRunResult(
            final_content=final_content,
            messages=conversation,
            tools_used=tools_used,
            tool_events=tool_events,
            trace=trace,
        )
