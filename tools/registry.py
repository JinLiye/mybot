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

    async def execute(self, name: str, arguments: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'"
        result = await tool.execute(**arguments)
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)
