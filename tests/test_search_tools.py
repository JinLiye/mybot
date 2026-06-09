import pytest

from tools.search import FindFilesTool, GrepTool


@pytest.mark.asyncio
async def test_find_files_filters_by_query_glob_and_type(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "src" / "app.md").write_text("hello", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.py").write_text("x", encoding="utf-8")

    result = await FindFilesTool(tmp_path).execute(query="app", type="py")

    assert result["truncated"] is False
    assert result["results"] == [{"path": "src/app.py", "type": "file"}]


@pytest.mark.asyncio
async def test_grep_searches_text_files_with_regex_and_filters(tmp_path) -> None:
    (tmp_path / "a.py").write_text("alpha = 1\nbeta = 2\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("alpha docs\n", encoding="utf-8")

    result = await GrepTool(tmp_path).execute(r"alpha\s*=", regex=True, type="py")

    assert result["truncated"] is False
    assert result["matches"] == [{"path": "a.py", "line": 1, "text": "alpha = 1"}]
