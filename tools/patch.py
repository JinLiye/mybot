"""Structured workspace patch tool."""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Any

from mybot.tools.base import Tool
from mybot.tools.filesystem import ConfirmOutsideWorkspace, WorkspaceTool

_ABSOLUTE_WINDOWS_RE = re.compile(r"^[A-Za-z]:[\\/]")


class PatchError(ValueError):
    pass


def _validate_patch_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    if not normalized:
        raise PatchError("patch path cannot be empty")
    if "\0" in normalized:
        raise PatchError("patch path contains a null byte")
    if normalized.startswith(("/", "~")) or _ABSOLUTE_WINDOWS_RE.match(normalized):
        raise PatchError(f"patch path must be workspace-relative: {path}")
    if any(part == ".." for part in normalized.split("/")):
        raise PatchError(f"patch path must not contain '..': {path}")
    return normalized


def _ensure_trailing_newline(text: str) -> str:
    if text and not text.endswith("\n"):
        return text + "\n"
    return text


def _line_diff_stats(before: str, after: str) -> tuple[int, int]:
    before_lines = before.replace("\r\n", "\n").splitlines()
    after_lines = after.replace("\r\n", "\n").splitlines()
    added = 0
    deleted = 0
    matcher = difflib.SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag in {"replace", "delete"}:
            deleted += i2 - i1
        if tag in {"replace", "insert"}:
            added += j2 - j1
    return added, deleted


def _unified_diff(path: str, before: str, after: str, *, max_lines: int = 200) -> list[str]:
    lines = list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )
    if len(lines) > max_lines:
        return lines[:max_lines] + [f"... diff truncated ({len(lines) - max_lines} more lines)"]
    return lines


class ApplyPatchTool(WorkspaceTool, Tool):
    @property
    def name(self) -> str:
        return "apply_patch"

    @property
    def description(self) -> str:
        return (
            "Apply structured code edits. Supports multiple add/replace edits, dry-run previews, "
            "and workspace-relative paths. Prefer this over shell redirection or sed for code changes. "
            "For large files, create or update them in smaller chunks with multiple add/replace edits "
            "instead of sending one huge new_text value."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "edits": {
                    "type": "array",
                    "description": "List of edits to apply. For large files, split content into smaller add/replace chunks.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Workspace-relative file path."},
                            "action": {"type": "string", "enum": ["add", "replace"]},
                            "old_text": {"type": "string", "description": "Exact text to replace."},
                            "new_text": {"type": "string", "description": "Text to add or replace with. Keep individual values reasonably small to avoid truncated tool JSON."},
                        },
                        "required": ["path", "action"],
                    },
                },
                "dry_run": {"type": "boolean", "description": "Preview without writing files."},
            },
            "required": ["edits"],
        }

    async def execute(self, edits: list[dict[str, Any]], dry_run: bool = False) -> dict[str, Any]:
        if not edits:
            raise PatchError("must provide at least one edit")
        pending: dict[Path, tuple[str, str]] = {}
        summaries: list[dict[str, Any]] = []
        diffs: list[str] = []

        for edit in edits:
            if not isinstance(edit, dict):
                raise PatchError("each edit must be an object")
            raw_path = edit.get("path")
            if not isinstance(raw_path, str):
                raise PatchError("edit path is required")
            relative_path = _validate_patch_path(raw_path)
            target = self._resolve_path(relative_path)
            action = edit.get("action")
            if action not in {"add", "replace"}:
                raise PatchError(f"unknown patch action for {relative_path}: {action}")

            before, current = pending.get(target, ("", ""))
            if target not in pending:
                if target.exists():
                    if not target.is_file():
                        raise PatchError(f"path is not a file: {relative_path}")
                    before = target.read_text(encoding="utf-8", errors="replace")
                    current = before
                else:
                    before = ""
                    current = ""

            if action == "add":
                new_text = edit.get("new_text")
                if new_text is None:
                    raise PatchError(f"new_text required for add: {relative_path}")
                after = _ensure_trailing_newline(current + str(new_text))
            else:
                old_text = edit.get("old_text")
                new_text = edit.get("new_text")
                if not old_text:
                    raise PatchError(f"old_text required for replace: {relative_path}")
                if new_text is None:
                    raise PatchError(f"new_text required for replace: {relative_path}")
                old = str(old_text)
                count = current.count(old)
                if count == 0:
                    raise PatchError(f"old_text not found in {relative_path}")
                if count > 1:
                    raise PatchError(f"old_text appears multiple times in {relative_path}")
                after = current.replace(old, str(new_text), 1)

            pending[target] = (before, after)
            added, deleted = _line_diff_stats(current, after)
            summaries.append(
                {
                    "path": relative_path,
                    "action": action,
                    "added": added,
                    "deleted": deleted,
                }
            )

        for target, (before, after) in pending.items():
            display = self._display_path(target)
            diffs.extend(_unified_diff(display, before, after))
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(after, encoding="utf-8")

        return {
            "dry_run": dry_run,
            "changed_files": [self._display_path(path) for path in pending],
            "edits": summaries,
            "diff": "\n".join(diffs),
        }


def register_patch_tools(
    registry: Any,
    workspace: Path,
    confirm_outside: ConfirmOutsideWorkspace | None = None,
) -> None:
    registry.register(ApplyPatchTool(workspace, confirm_outside=confirm_outside))
