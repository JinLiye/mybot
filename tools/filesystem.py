"""Workspace-scoped filesystem tools."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from mybot.tools.base import Tool

ConfirmOutsideWorkspace = Callable[[Path, Path, str], bool]


def confirm_outside_workspace(candidate: Path, workspace: Path, original_path: str) -> bool:
    print("\nTool requested a path outside the current workspace.")
    print(f"workspace: {workspace}")
    print(f"requested: {candidate}")
    answer = input(f"Allow this tool access for {original_path!r}? [y/N] ").strip().lower()
    return answer in {"y", "yes"}



class WorkspaceTool:
    def __init__(
        self,
        workspace: Path,
        confirm_outside: ConfirmOutsideWorkspace | None = None,
    ) -> None:
        self.workspace = workspace.expanduser().resolve()
        self.confirm_outside = confirm_outside

    def _resolve_path(self, path: str = ".") -> Path:
        raw = Path(path).expanduser()
        candidate = raw.resolve() if raw.is_absolute() else (self.workspace / raw).resolve()
        if self._inside_workspace(candidate):
            return candidate
        if self.confirm_outside and self.confirm_outside(candidate, self.workspace, path):
            return candidate
        raise PermissionError(f"Path is outside workspace: {path}")

    def _inside_workspace(self, path: Path) -> bool:
        return path == self.workspace or self.workspace in path.parents

    def _display_path(self, path: Path) -> str:
        if self._inside_workspace(path):
            return str(path.relative_to(self.workspace))
        return str(path)


class ListDirTool(WorkspaceTool, Tool):
    @property
    def name(self) -> str:
        return "list_dir"

    @property
    def description(self) -> str:
        return "List files and directories. Paths inside workspace run directly; outside paths require user confirmation."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path inside the workspace, or an absolute path that requires user confirmation.",
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
        return {"path": self._display_path(target), "entries": entries}


class ReadFileTool(WorkspaceTool, Tool):
    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read a UTF-8 text file. Workspace files run directly; outside files require user confirmation."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative file path inside the workspace, or an absolute path that requires user confirmation.",
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
            "path": self._display_path(target),
            "content": content,
            "truncated": truncated,
        }


class SearchTextTool(WorkspaceTool, Tool):
    @property
    def name(self) -> str:
        return "search_text"

    @property
    def description(self) -> str:
        return "Search UTF-8 text files. Workspace paths run directly; outside paths require user confirmation."

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
                    "description": "Relative directory path inside the workspace, or an absolute path that requires user confirmation.",
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
            relative = self._display_path(file_path)
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


def register_filesystem_tools(
    registry: Any,
    workspace: Path,
    confirm_outside: ConfirmOutsideWorkspace | None = confirm_outside_workspace,
) -> None:
    registry.register(ListDirTool(workspace, confirm_outside=confirm_outside))
    registry.register(ReadFileTool(workspace, confirm_outside=confirm_outside))
    registry.register(SearchTextTool(workspace, confirm_outside=confirm_outside))
