"""CLI entrypoint for mybot."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from uuid import uuid4

from mybot.config import BotConfig
from mybot.events import InboundMessage
from mybot.loop import AgentLoop
from mybot.session import SessionSummary


@dataclass(slots=True)
class CliState:
    chat_id: str


def _shorten(text: str, limit: int = 42) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def _chat_id_from_key(key: str) -> str:
    prefix = "cli:"
    return key[len(prefix):] if key.startswith(prefix) else key


def _format_session(summary: SessionSummary) -> str:
    title = summary.title or "(untitled)"
    first = _shorten(summary.first_user_message) or "(no user message)"
    return f"{title} | id={_chat_id_from_key(summary.key)} | first={first}"


def _select_session(sessions: list[SessionSummary]) -> SessionSummary | None:
    if not sessions:
        print("No saved sessions.")
        return None
    try:
        import questionary
    except Exception:
        for index, summary in enumerate(sessions, start=1):
            print(f"{index}. {_format_session(summary)}")
        raw = input("session> ").strip()
        if not raw.isdigit():
            return None
        index = int(raw)
        if not 1 <= index <= len(sessions):
            return None
        return sessions[index - 1]

    choices = [
        questionary.Choice(title=_format_session(summary), value=summary)
        for summary in sessions
    ]
    return questionary.select("Resume session", choices=choices).ask()


def _print_help() -> None:
    print("Commands:")
    print("  /help              Show this menu")
    print("  /resume            Select a saved session")
    print("  /rename <name>     Rename current session")
    print("  /new               Start a new session")
    print("  /session           Show current session id")
    print("  /exit              Quit")


async def _chat(provider_name: str | None = None) -> None:
    config = BotConfig.from_env()
    if provider_name:
        if provider_name.lower() == "bailian":
            import os

            os.environ["MYBOT_PROVIDER"] = "bailian"
            config = BotConfig.from_env()
        elif provider_name.lower() == "vllm":
            import os

            os.environ["MYBOT_PROVIDER"] = "vllm"
            config = BotConfig.from_env()
    loop = AgentLoop(config)
    state = CliState(chat_id=str(uuid4()))

    print(f"mybot provider={config.provider.name} model={config.provider.model}")
    print("Type /help for commands. Type /exit to stop.")

    while True:
        user_text = input("you> ").strip()
        command = user_text.lower()
        if command in {"exit", "quit", "/exit", "/quit"}:
            break
        if command == "/help":
            _print_help()
            continue
        if command == "/session":
            print(f"Current session id: {state.chat_id}")
            continue
        if command == "/new":
            state.chat_id = str(uuid4())
            print(f"Started new session: {state.chat_id}")
            continue
        if command == "/resume":
            selected = _select_session(loop.sessions.list_sessions())
            if selected is None:
                continue
            state.chat_id = _chat_id_from_key(selected.key)
            print(f"Resumed: {_format_session(selected)}")
            continue
        if command == "/rename" or command.startswith("/rename "):
            title = user_text[len("/rename"):].strip()
            if not title:
                title = input("name> ").strip()
            if not title:
                print("Rename skipped.")
                continue
            session = loop.sessions.get_or_create(f"cli:{state.chat_id}")
            session.rename(title)
            loop.sessions.save(session)
            print(f"Renamed current session to: {title}")
            continue
        if user_text.startswith("/"):
            print("Unknown command. Type /help for commands.")
            continue
        inbound = InboundMessage(
            channel="cli",
            sender_id="local-user",
            chat_id=state.chat_id,
            content=user_text,
        )
        outbound = await loop.process(inbound)
        print(f"bot> {outbound.content}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run mybot in local CLI mode.")
    parser.add_argument(
        "--provider",
        choices=["vllm", "bailian"],
        help="Provider profile to use. Overrides MYBOT_PROVIDER for this run.",
    )
    args = parser.parse_args()
    asyncio.run(_chat(provider_name=args.provider))


if __name__ == "__main__":
    main()
