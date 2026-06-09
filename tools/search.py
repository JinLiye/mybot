"""Workspace search tools for code navigation."""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from mybot.tools.base import Tool
from mybot.tools.filesystem import ConfirmOutsideWorkspace, WorkspaceTool

_IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".data",
}
_TYPE_GLOBS = {
    "py": ("*.py", "*.pyi"),
    "python": ("*.py", "*.pyi"),
    "js": ("*.js", "*.jsx", "*.mjs", "*.cjs"),
    "ts": ("*.ts", "*.tsx", "*.mts", "*.cts"),
    "json": ("*.json",),
    "md": ("*.md", "*.mdx"),
    "yaml": ("*.yaml", "*.yml"),
    "toml": ("*.toml",),
    "sh": ("*.sh", "*.bash"),
    "html": ("*.html", "*.htm"),
    "css": ("*.css", "*.scss", "*.sass"),
}


def _coerce_limit(value: int | None, *, default: int, upper: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return upper
    return min(parsed, upper)


def _matches_glob(rel_path: str, name: str, pattern: str | None) -> bool:
    if not pattern:
        return True
    normalized = pattern.strip().replace("\\", "/")
    if not normalized:
        return True
    if "/" in normalized or normalized.startswith("**"):
        return PurePosixPath(rel_path).match(normalized)
    return fnmatch.fnmatch(name, normalized)


def _matches_type(name: str, file_type: str | None) -> bool:
    if not file_type:
        return True
    lowered = file_type.strip().lower()
    if not lowered:
        return True
    patterns = _TYPE_GLOBS.get(lowered, (f"*.{lowered}",))
    return any(fnmatch.fnmatch(name.lower(), pattern.lower()) for pattern in patterns)


def _is_probably_binary(path: Path) -> bool:
    try:
        raw = path.read_bytes()[:4096]
    except OSError:
        return True
    return b"\0" in raw


class SearchWorkspaceTool(WorkspaceTool):
    def _iter_paths(self, root: Path, *, include_dirs: bool = False) -> Iterable[Path]:
        if root.is_file():
            yield root
            return
        if include_dirs:
            yield root
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(dirname for dirname in dirnames if dirname not in _IGNORE_DIRS)
            current = Path(dirpath)
            if include_dirs and current != root:
                yield current
            for filename in sorted(filenames):
                yield current / filename


class FindFilesTool(SearchWorkspaceTool, Tool):
    @property
    def name(self) -> str:
        return "find_files"

    @property
    def description(self) -> str:
        return (
            "Find files by path fragment, glob, or file type. Prefer this over shell find/ls "
            "for ordinary workspace discovery."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory or file to search in."},
                "query": {"type": "string", "description": "Case-insensitive path fragment search."},
                "glob": {"type": "string", "description": "Glob filter, e.g. '*.py' or 'tests/**/test_*.py'."},
                "type": {"type": "string", "description": "File type shorthand, e.g. py, ts, md, json."},
                "include_dirs": {"type": "boolean", "description": "Include directories in results."},
                "limit": {"type": "integer", "description": "Maximum paths to return, default 100, max 1000."},
            },
        }

    async def execute(
        self,
        path: str = ".",
        query: str | None = None,
        glob: str | None = None,
        type: str | None = None,
        include_dirs: bool = False,
        limit: int | None = None,
    ) -> dict[str, Any]:
        target = self._resolve_path(path or ".")
        if not target.exists():
            return {"path": path, "error": "path does not exist"}
        max_results = _coerce_limit(limit, default=100, upper=1000)
        terms = [term for term in (query or "").lower().split() if term]
        results: list[dict[str, Any]] = []
        for candidate in self._iter_paths(target, include_dirs=include_dirs):
            rel = self._display_path(candidate).replace("\\", "/")
            if terms and not all(term in rel.lower() for term in terms):
                continue
            if not _matches_glob(rel, candidate.name, glob):
                continue
            if candidate.is_file() and not _matches_type(candidate.name, type):
                continue
            if candidate.is_dir() and type:
                continue
            results.append({"path": rel, "type": "directory" if candidate.is_dir() else "file"})
            if len(results) >= max_results:
                return {"path": self._display_path(target), "results": results, "truncated": True}
        return {"path": self._display_path(target), "results": results, "truncated": False}


class GrepTool(SearchWorkspaceTool, Tool):
    @property
    def name(self) -> str:
        return "grep"

    @property
    def description(self) -> str:
        return (
            "Search text files with plain text or regex. Prefer this over shell grep/rg "
            "so results stay workspace-scoped and structured."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Text or regex pattern to search for."},
                "path": {"type": "string", "description": "Directory or file to search in."},
                "glob": {"type": "string", "description": "Optional glob filter, e.g. '*.py'."},
                "type": {"type": "string", "description": "Optional file type shorthand, e.g. py, md, json."},
                "regex": {"type": "boolean", "description": "Interpret pattern as regex, default false."},
                "case_sensitive": {"type": "boolean", "description": "Case-sensitive search, default false."},
                "limit": {"type": "integer", "description": "Maximum matches to return, default 50, max 500."},
            },
            "required": ["pattern"],
        }

    async def execute(
        self,
        pattern: str,
        path: str = ".",
        glob: str | None = None,
        type: str | None = None,
        regex: bool = False,
        case_sensitive: bool = False,
        limit: int | None = None,
    ) -> dict[str, Any]:
        target = self._resolve_path(path or ".")
        if not target.exists():
            return {"path": path, "pattern": pattern, "error": "path does not exist"}
        max_results = _coerce_limit(limit, default=50, upper=500)
        flags = 0 if case_sensitive else re.IGNORECASE
        compiled = re.compile(pattern, flags) if regex else None
        needle = pattern if case_sensitive else pattern.lower()
        matches: list[dict[str, Any]] = []
        for candidate in self._iter_paths(target):
            if not candidate.is_file() or _is_probably_binary(candidate):
                continue
            rel = self._display_path(candidate).replace("\\", "/")
            if not _matches_glob(rel, candidate.name, glob):
                continue
            if not _matches_type(candidate.name, type):
                continue
            try:
                lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line_number, line in enumerate(lines, start=1):
                haystack = line if case_sensitive else line.lower()
                found = compiled.search(line) if compiled else needle in haystack
                if not found:
                    continue
                matches.append({"path": rel, "line": line_number, "text": line.strip()})
                if len(matches) >= max_results:
                    return {"pattern": pattern, "matches": matches, "truncated": True}
        return {"pattern": pattern, "matches": matches, "truncated": False}


def register_search_tools(
    registry: Any,
    workspace: Path,
    confirm_outside: ConfirmOutsideWorkspace | None = None,
) -> None:
    registry.register(FindFilesTool(workspace, confirm_outside=confirm_outside))
    registry.register(GrepTool(workspace, confirm_outside=confirm_outside))
