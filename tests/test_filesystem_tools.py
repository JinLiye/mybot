import json

import pytest

from tools.filesystem import ListDirTool, ReadFileTool, SearchTextTool
from tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_filesystem_tools_reject_outside_workspace_by_default(tmp_path) -> None:
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    tool = ReadFileTool(tmp_path, confirm_outside=None)

    with pytest.raises(PermissionError, match="outside workspace"):
        await tool.execute("../outside.txt")


@pytest.mark.asyncio
async def test_filesystem_tools_allow_outside_workspace_after_confirmation(tmp_path) -> None:
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    calls = []

    def confirm(candidate, workspace, original_path):
        calls.append((candidate, workspace, original_path))
        return True

    result = await ReadFileTool(tmp_path, confirm_outside=confirm).execute("../outside.txt")

    assert result["path"] == str(outside.resolve())
    assert result["content"] == "secret"
    assert calls and calls[0][2] == "../outside.txt"


@pytest.mark.asyncio
async def test_list_dir_and_read_file(tmp_path) -> None:
    (tmp_path / "README.md").write_text("hello mybot", encoding="utf-8")
    (tmp_path / "src").mkdir()

    listed = await ListDirTool(tmp_path).execute(".")
    read = await ReadFileTool(tmp_path).execute("README.md")

    assert listed["entries"][0] == {"name": "src", "type": "directory"}
    assert {"name": "README.md", "type": "file"} in listed["entries"]
    assert read["content"] == "hello mybot"
    assert read["truncated"] is False


@pytest.mark.asyncio
async def test_search_text_returns_matching_lines(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("alpha\nneedle one\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("needle two\nbeta\n", encoding="utf-8")

    result = await SearchTextTool(tmp_path).execute("needle")

    assert result["truncated"] is False
    assert [match["path"] for match in result["matches"]] == ["a.txt", "b.txt"]


@pytest.mark.asyncio
async def test_registry_executes_filesystem_tool_as_json(tmp_path) -> None:
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    registry = ToolRegistry()
    registry.register(ReadFileTool(tmp_path))

    raw = await registry.execute("read_file", {"path": "README.md"})

    assert json.loads(raw)["content"] == "hello"
