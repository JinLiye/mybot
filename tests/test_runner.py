import json

import pytest

from providers.base import LLMResponse, ToolCallRequest
from runner import AgentRunner
from tools.base import Tool
from tools.registry import ToolRegistry


class FakeProvider:
    def __init__(self, responses):
        self._responses = list(responses)

    async def chat(self, messages, *, tools=None, max_tokens=2048, temperature=0.2):
        return self._responses.pop(0)


class EchoTool(Tool):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo the provided text."

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        }

    async def execute(self, **kwargs):
        return {"echo": kwargs["text"]}


@pytest.mark.asyncio
async def test_runner_executes_tool_calls_then_returns_final_content() -> None:
    provider = FakeProvider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCallRequest(id="1", name="echo", arguments={"text": "hello"})],
                finish_reason="tool_calls",
            ),
            LLMResponse(content="done", finish_reason="stop"),
        ]
    )
    tools = ToolRegistry()
    tools.register(EchoTool())
    runner = AgentRunner(provider)

    result = await runner.run(
        [{"role": "system", "content": "test"}, {"role": "user", "content": "hi"}],
        tools=tools,
        max_iterations=3,
        max_tokens=256,
        temperature=0.1,
    )

    assert result.final_content == "done"
    assert result.tools_used == ["echo"]
    assert any(message.get("role") == "tool" for message in result.messages)
    tool_message = next(message for message in result.messages if message.get("role") == "tool")
    assert json.loads(tool_message["content"]) == {"echo": "hello"}
