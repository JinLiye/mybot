from providers.openai_compat import parse_tool_arguments


def test_parse_tool_arguments_returns_dict_for_valid_json() -> None:
    assert parse_tool_arguments('{"path": "game/index.html"}') == {"path": "game/index.html"}


def test_parse_tool_arguments_marks_invalid_json_without_raising() -> None:
    parsed = parse_tool_arguments('{"path": "game/index.html", "content": "unterminated')

    assert parsed["_invalid_tool_arguments"] is True
    assert "invalid JSON tool arguments" in parsed["error"]


def test_parse_tool_arguments_requires_object() -> None:
    parsed = parse_tool_arguments('["not", "object"]')

    assert parsed["_invalid_tool_arguments"] is True
    assert "object" in parsed["error"]
