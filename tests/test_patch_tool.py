import pytest

from tools.patch import ApplyPatchTool, PatchError


@pytest.mark.asyncio
async def test_apply_patch_dry_run_does_not_write(tmp_path) -> None:
    path = tmp_path / "app.py"
    path.write_text("print('old')\n", encoding="utf-8")
    tool = ApplyPatchTool(tmp_path)

    result = await tool.execute(
        edits=[
            {
                "path": "app.py",
                "action": "replace",
                "old_text": "print('old')",
                "new_text": "print('new')",
            }
        ],
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert "print('new')" in result["diff"]
    assert path.read_text(encoding="utf-8") == "print('old')\n"


@pytest.mark.asyncio
async def test_apply_patch_writes_add_and_replace(tmp_path) -> None:
    path = tmp_path / "app.py"
    path.write_text("print('old')\n", encoding="utf-8")
    tool = ApplyPatchTool(tmp_path)

    result = await tool.execute(
        edits=[
            {
                "path": "app.py",
                "action": "replace",
                "old_text": "print('old')",
                "new_text": "print('new')",
            },
            {
                "path": "notes.md",
                "action": "add",
                "new_text": "hello notes",
            },
        ]
    )

    assert sorted(result["changed_files"]) == ["app.py", "notes.md"]
    assert path.read_text(encoding="utf-8") == "print('new')\n"
    assert (tmp_path / "notes.md").read_text(encoding="utf-8") == "hello notes\n"


@pytest.mark.asyncio
async def test_apply_patch_rejects_parent_paths(tmp_path) -> None:
    tool = ApplyPatchTool(tmp_path)

    with pytest.raises(PatchError, match="must not contain"):
        await tool.execute(edits=[{"path": "../escape.txt", "action": "add", "new_text": "x"}])
