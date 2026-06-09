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



def test_session_store_persists_memory_summary(tmp_path) -> None:
    store = SessionStore(tmp_path)
    session = store.get_or_create("cli:test")
    session.add_message("user", "old")
    session.add_message("assistant", "reply")
    session.set_memory_summary("User is building mybot.", 2)
    store.save(session)

    reloaded = store.get_or_create("cli:test")

    assert reloaded.memory_summary == "User is building mybot."
    assert reloaded.memory_summary_message_count == 2
    assert reloaded.memory_updated_at


def test_session_context_history_skips_summarized_messages(tmp_path) -> None:
    store = SessionStore(tmp_path)
    session = store.get_or_create("cli:test")
    session.add_message("user", "old")
    session.add_message("assistant", "old reply")
    session.add_message("user", "recent")
    session.set_memory_summary("old summary", 2)

    history = session.get_context_history(20)

    assert [message["content"] for message in history] == ["recent"]
