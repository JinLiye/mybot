import pytest

from tools.shell import ShellExecTool


@pytest.mark.asyncio
async def test_shell_exec_runs_in_workspace(tmp_path) -> None:
    tool = ShellExecTool(tmp_path, confirm_exec=lambda command, cwd: True)

    result = await tool.execute("printf hello")

    assert result["cwd"] == "."
    assert result["exit_code"] == 0
    assert result["stdout"] == "hello"
    assert result["timed_out"] is False


@pytest.mark.asyncio
async def test_shell_exec_rejects_without_confirmation(tmp_path) -> None:
    tool = ShellExecTool(tmp_path, confirm_exec=lambda command, cwd: False)

    with pytest.raises(PermissionError, match="not allowed"):
        await tool.execute("printf hello")


@pytest.mark.asyncio
async def test_shell_exec_uses_relative_cwd(tmp_path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    tool = ShellExecTool(tmp_path, confirm_exec=lambda command, cwd: True)

    result = await tool.execute("pwd", cwd="work")

    assert result["cwd"] == "work"
    assert result["stdout"].strip() == str(work)


@pytest.mark.asyncio
async def test_shell_exec_rejects_outside_workspace_by_default(tmp_path) -> None:
    outside = tmp_path.parent
    tool = ShellExecTool(tmp_path, confirm_exec=lambda command, cwd: True, confirm_outside=None)

    with pytest.raises(PermissionError, match="outside workspace"):
        await tool.execute("pwd", cwd=str(outside))


@pytest.mark.asyncio
async def test_shell_exec_allows_outside_workspace_after_confirmation(tmp_path) -> None:
    outside = tmp_path.parent

    def confirm_outside(candidate, workspace, original_path):
        return True

    tool = ShellExecTool(
        tmp_path,
        confirm_exec=lambda command, cwd: True,
        confirm_outside=confirm_outside,
    )

    result = await tool.execute("pwd", cwd=str(outside))

    assert result["cwd"] == str(outside.resolve())
    assert result["stdout"].strip() == str(outside.resolve())


@pytest.mark.asyncio
async def test_shell_exec_truncates_output(tmp_path) -> None:
    tool = ShellExecTool(tmp_path, confirm_exec=lambda command, cwd: True)

    result = await tool.execute("printf abcdef", max_output_chars=3)

    assert result["stdout"] == "abc"
    assert result["stdout_truncated"] is True


@pytest.mark.asyncio
async def test_shell_exec_times_out(tmp_path) -> None:
    tool = ShellExecTool(tmp_path, confirm_exec=lambda command, cwd: True)

    result = await tool.execute("sleep 2", timeout_seconds=1)

    assert result["timed_out"] is True
