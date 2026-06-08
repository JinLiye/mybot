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


def test_session_store_lists_sessions_with_title_and_first_user_message(tmp_path) -> None:
    store = SessionStore(tmp_path)
    session = store.get_or_create("cli:test")
    session.rename("Work chat")
    session.add_message("user", "hello this is the first question")
    session.add_message("assistant", "world")
    store.save(session)

    summaries = store.list_sessions()

    assert len(summaries) == 1
    assert summaries[0].key == "cli:test"
    assert summaries[0].title == "Work chat"
    assert summaries[0].first_user_message == "hello this is the first question"
    assert summaries[0].message_count == 2
