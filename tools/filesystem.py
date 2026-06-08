"""Workspace-scoped filesystem tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mybot.tools.base import Tool


class WorkspaceTool:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.expanduser().resolve()

    def _resolve_path(self, path: str = ".") -> Path:
        candidate = (self.workspace / path).expanduser().resolve()
        if candidate != self.workspace and self.workspace not in candidate.parents:
            raise ValueError(f"Path is outside workspace: {path}")
        return candidate


class ListDirTool(WorkspaceTool, Tool):
    @property
    def name(self) -> str:
        return "list_dir"

    @property
    def description(self) -> str:
        return "List files and directories under the configured workspace."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path inside the workspace. Defaults to '.'.",
                }
            },
        }

    async def execute(self, path: str = ".") -> dict[str, Any]:
        target = self._resolve_path(path)
        if not target.exists():
            return {"path": path, "error": "path does not exist"}
        if not target.is_dir():
            return {"path": path, "error": "path is not a directory"}
        entries = []
        for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            entries.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
            })
        return {"path": str(target.relative_to(self.workspace)), "entries": entries}


class ReadFileTool(WorkspaceTool, Tool):
    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read a UTF-8 text file under the configured workspace."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative file path inside the workspace.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum number of characters to return.",
                    "default": 12000,
                },
            },
            "required": ["path"],
        }

    async def execute(self, path: str, max_chars: int = 12000) -> dict[str, Any]:
        target = self._resolve_path(path)
        if not target.exists():
            return {"path": path, "error": "file does not exist"}
        if not target.is_file():
            return {"path": path, "error": "path is not a file"}
        content = target.read_text(encoding="utf-8", errors="replace")
        truncated = len(content) > max_chars
        if truncated:
            content = content[:max_chars]
        return {
            "path": str(target.relative_to(self.workspace)),
            "content": content,
            "truncated": truncated,
        }


class SearchTextTool(WorkspaceTool, Tool):
    @property
    def name(self) -> str:
        return "search_text"

    @property
    def description(self) -> str:
        return "Search UTF-8 text files under the configured workspace for a query string."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to search for.",
                },
                "path": {
                    "type": "string",
                    "description": "Relative directory path inside the workspace. Defaults to '.'.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of matching lines to return.",
                    "default": 20,
                },
            },
            "required": ["query"],
        }

    async def execute(
        self,
        query: str,
        path: str = ".",
        max_results: int = 20,
    ) -> dict[str, Any]:
        target = self._resolve_path(path)
        if not target.exists():
            return {"path": path, "query": query, "error": "path does not exist"}
        if target.is_file():
            candidates = [target]
        else:
            candidates = [item for item in target.rglob("*") if item.is_file()]

        matches: list[dict[str, Any]] = []
        for file_path in candidates:
            relative = str(file_path.relative_to(self.workspace))
            try:
                lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line_number, line in enumerate(lines, start=1):
                if query in line:
                    matches.append({
                        "path": relative,
                        "line": line_number,
                        "text": line.strip(),
                    })
                    if len(matches) >= max_results:
                        return {"query": query, "matches": matches, "truncated": True}
        return {"query": query, "matches": matches, "truncated": False}


def register_filesystem_tools(registry: Any, workspace: Path) -> None:
    registry.register(ListDirTool(workspace))
    registry.register(ReadFileTool(workspace))
    registry.register(SearchTextTool(workspace))
