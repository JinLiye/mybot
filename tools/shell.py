"""Workspace-aware shell execution tool."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mybot.tools.base import Tool
from mybot.tools.filesystem import ConfirmOutsideWorkspace, WorkspaceTool

ConfirmShellExec = Callable[[str, Path], bool]


def confirm_shell_exec(command: str, cwd: Path) -> bool:
    print("\nTool requested shell execution.")
    print(f"cwd: {cwd}")
    print(f"command: {command}")
    answer = input("Allow this shell command? [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def _coerce_positive_int(value: int, *, default: int, upper: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return min(parsed, upper)


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit], True


class ShellExecTool(WorkspaceTool, Tool):
    def __init__(
        self,
        workspace: Path,
        confirm_exec: ConfirmShellExec | None,
        confirm_outside: ConfirmOutsideWorkspace | None = None,
    ) -> None:
        super().__init__(workspace, confirm_outside=confirm_outside)
        self.confirm_exec = confirm_exec

    @property
    def name(self) -> str:
        return "shell_exec"

    @property
    def description(self) -> str:
        return (
            "Run a one-shot shell command. The cwd is workspace-relative by default; "
            "permission mode controls whether shell execution is rejected, confirmed, or allowed."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute.",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory, relative to the workspace unless absolute.",
                    "default": ".",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Maximum execution time before the process is killed.",
                    "default": 30,
                },
                "max_output_chars": {
                    "type": "integer",
                    "description": "Maximum characters to keep for each output stream.",
                    "default": 12000,
                },
            },
            "required": ["command"],
        }

    async def execute(
        self,
        command: str,
        cwd: str = ".",
        timeout_seconds: int = 30,
        max_output_chars: int = 12000,
    ) -> dict[str, Any]:
        resolved_cwd = self._resolve_path(cwd)
        if not resolved_cwd.exists():
            return {"command": command, "cwd": cwd, "error": "cwd does not exist"}
        if not resolved_cwd.is_dir():
            return {"command": command, "cwd": cwd, "error": "cwd is not a directory"}
        if not self.confirm_exec or not self.confirm_exec(command, resolved_cwd):
            raise PermissionError("Shell execution was not allowed")

        timeout = _coerce_positive_int(timeout_seconds, default=30, upper=300)
        output_limit = _coerce_positive_int(max_output_chars, default=12000, upper=50000)
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=str(resolved_cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        timed_out = False
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
        except TimeoutError:
            timed_out = True
            process.kill()
            stdout_bytes, stderr_bytes = await process.communicate()

        stdout, stdout_truncated = _truncate(
            stdout_bytes.decode("utf-8", errors="replace"),
            output_limit,
        )
        stderr, stderr_truncated = _truncate(
            stderr_bytes.decode("utf-8", errors="replace"),
            output_limit,
        )
        return {
            "command": command,
            "cwd": self._display_path(resolved_cwd),
            "exit_code": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "timed_out": timed_out,
        }


def register_shell_tools(
    registry: Any,
    workspace: Path,
    confirm_exec: ConfirmShellExec | None,
    confirm_outside: ConfirmOutsideWorkspace | None = None,
) -> None:
    registry.register(
        ShellExecTool(
            workspace,
            confirm_exec=confirm_exec,
            confirm_outside=confirm_outside,
        )
    )
