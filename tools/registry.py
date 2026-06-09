"""Tool registry for mybot."""

from __future__ import annotations

import json
from typing import Any

from mybot.tools.base import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get_definitions(self) -> list[dict[str, Any]]:
        return [self._tools[name].to_schema() for name in sorted(self._tools)]

    def get_summaries(self) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for name in sorted(self._tools):
            tool = self._tools[name]
            summaries.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            })
        return summaries

    async def execute(self, name: str, arguments: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'"
        if arguments.get("_invalid_tool_arguments"):
            return (
                f"Error: invalid arguments for tool '{name}': {arguments.get('error', 'unknown parse error')}. "
                "The model should retry the tool call with valid JSON arguments."
            )
        result = await tool.execute(**arguments)
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)
