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


class Style:
    RESET = "\033[0m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    RED = "\033[31m"


def _style(text: str, *codes: str) -> str:
    return "".join(codes) + text + Style.RESET


def _render_block(label: str, content: str, color: str) -> None:
    print(_style(f"\n[{label}]", Style.BOLD, color))
    print(content)


def _render_status(message: str) -> None:
    print(_style(f":: {message}", Style.DIM, Style.CYAN))


def _render_error(message: str) -> None:
    print(_style(f"!! {message}", Style.BOLD, Style.RED))


def _render_tool(message: str) -> None:
    print(_style(f"tool> {message}", Style.MAGENTA))


def _render_tool_events(events: list[dict]) -> None:
    for event in events:
        name = event.get("name", "unknown")
        duration = event.get("duration_ms", 0)
        arguments = event.get("arguments", {})
        preview = event.get("result_preview", "")
        error = event.get("error")
        _render_tool(f"{name} {arguments} ({duration}ms)")
        if error:
            _render_error(f"tool error: {error}")
        elif preview:
            print(_style(f"tool< {preview}", Style.DIM, Style.MAGENTA))


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


def _render_history(messages: list[dict], *, limit: int) -> None:
    if not messages:
        _render_status("No previous messages in this session.")
        return
    visible = messages[-limit:] if limit > 0 else messages
    hidden = len(messages) - len(visible)
    _render_status("session history")
    if hidden > 0:
        _render_status(f"... {hidden} earlier message(s) hidden")
    for message in visible:
        role = message.get("role")
        content = str(message.get("content") or "").strip()
        if not content or role not in {"user", "assistant"}:
            continue
        if role == "user":
            _render_block("you", content, Style.GREEN)
        else:
            events = message.get("tool_events")
            if isinstance(events, list) and events:
                _render_tool_events(events)
            _render_block("bot", content, Style.CYAN)
    _render_status("continue")


async def _select_session(sessions: list[SessionSummary]) -> SessionSummary | None:
    if not sessions:
        _render_status("No saved sessions.")
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
    return await questionary.select("Resume session", choices=choices).ask_async()


def _render_tools(loop: AgentLoop) -> None:
    _render_status(
        f"tools={'on' if loop.tools_enabled else 'off'} permission={loop.tool_permission_mode}"
    )
    for summary in loop.tools.get_summaries():
        params = summary.get("parameters", {})
        required = params.get("required", []) if isinstance(params, dict) else []
        required_text = f" required={required}" if required else ""
        print(_style(summary["name"], Style.BOLD, Style.MAGENTA))
        print(f"  {summary['description']}{required_text}")


def _render_permissions(loop: AgentLoop) -> None:
    _render_status(f"tool permission mode: {loop.tool_permission_mode}")
    print("  strict  Reject filesystem paths outside workspace")
    print("  ask     Ask before filesystem paths outside workspace")
    print("  open    Allow filesystem paths outside workspace")


def _print_help() -> None:
    _render_status("Commands")
    print("  /help              Show this menu")
    print("  /resume            Select a saved session")
    print("  /tools             Show available tools and current tool state")
    print("  /tools on|off      Enable or disable tool calling")
    print("  /permissions       Show tool permission mode")
    print("  /permissions <mode>  Set strict, ask, or open")
    print("  /rename <name>     Rename current session")
    print("  /new               Start a new session")
    print("  /session           Show current session id")
    print("  /workspace         Show current tool workspace")
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

    _render_status(f"mybot provider={config.provider.name} model={config.provider.model}")
    _render_status(f"workspace={config.workspace}")
    _render_status("Type /help for commands. Type /exit to stop.")

    while True:
        user_text = input("you> ").strip()
        command = user_text.lower()
        if command in {"exit", "quit", "/exit", "/quit"}:
            break
        if command == "/help":
            _print_help()
            continue
        if command == "/session":
            _render_status(f"Current session id: {state.chat_id}")
            continue
        if command == "/workspace":
            _render_status(f"Current workspace: {config.workspace}")
            continue
        if command == "/tools":
            _render_tools(loop)
            continue
        if command in {"/tools on", "/tools off"}:
            loop.tools_enabled = command.endswith(" on")
            _render_status(f"tools {'enabled' if loop.tools_enabled else 'disabled'}")
            continue
        if command == "/permissions":
            _render_permissions(loop)
            continue
        if command.startswith("/permissions "):
            mode = command.split(maxsplit=1)[1]
            try:
                loop.set_tool_permission_mode(mode)
            except ValueError as exc:
                _render_error(str(exc))
            else:
                _render_status(f"tool permission mode set to: {loop.tool_permission_mode}")
            continue
        if command == "/new":
            state.chat_id = str(uuid4())
            _render_status(f"Started new session: {state.chat_id}")
            continue
        if command == "/resume":
            selected = await _select_session(loop.sessions.list_sessions())
            if selected is None:
                continue
            state.chat_id = _chat_id_from_key(selected.key)
            _render_status(f"Resumed: {_format_session(selected)}")
            session = loop.sessions.get_or_create(selected.key)
            _render_history(session.messages, limit=config.max_history_messages)
            continue
        if command == "/rename" or command.startswith("/rename "):
            title = user_text[len("/rename"):].strip()
            if not title:
                title = input("name> ").strip()
            if not title:
                _render_status("Rename skipped.")
                continue
            session = loop.sessions.get_or_create(f"cli:{state.chat_id}")
            session.rename(title)
            loop.sessions.save(session)
            _render_status(f"Renamed current session to: {title}")
            continue
        if user_text.startswith("/"):
            _render_error("Unknown command. Type /help for commands.")
            continue
        inbound = InboundMessage(
            channel="cli",
            sender_id="local-user",
            chat_id=state.chat_id,
            content=user_text,
        )
        outbound = await loop.process(inbound)
        events = outbound.metadata.get("tool_events")
        if isinstance(events, list) and events:
            _render_tool_events(events)
        _render_block("bot", outbound.content, Style.CYAN)


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
