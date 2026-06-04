from session import SessionStore


def test_session_store_persists_messages(tmp_path) -> None:
    store = SessionStore(tmp_path)
    session = store.get_or_create("cli:test")
    session.add_message("user", "hello")
    session.add_message("assistant", "world")
    store.save(session)

    reloaded = store.get_or_create("cli:test")

    assert [item["role"] for item in reloaded.messages] == ["user", "assistant"]
    assert reloaded.messages[0]["content"] == "hello"
