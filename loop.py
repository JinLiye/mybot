"""Main orchestration loop for mybot."""

from __future__ import annotations

from pathlib import Path

from mybot.bus import MessageBus
from mybot.config import BotConfig
from mybot.context import ContextBuilder
from mybot.events import InboundMessage, OutboundMessage
from mybot.providers.openai_compat import OpenAICompatProvider
from mybot.runner import AgentRunner
from mybot.session import Session, SessionStore
from mybot.tools.filesystem import confirm_outside_workspace, register_filesystem_tools
from mybot.tools.patch import register_patch_tools
from mybot.tools.registry import ToolRegistry
from mybot.tools.search import register_search_tools
from mybot.tools.shell import confirm_shell_exec, register_shell_tools


class AgentLoop:
    """Small orchestrator inspired by nanobot's layering."""

    VALID_TOOL_PERMISSION_MODES = {"strict", "ask", "open"}

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.bus = MessageBus()
        self.context = ContextBuilder(config.system_prompt)
        self.sessions = SessionStore(config.session_dir)
        self.provider = OpenAICompatProvider(
            api_key=config.provider.api_key,
            api_base=config.provider.api_base,
            model=config.provider.model,
        )
        self.tools_enabled = True
        self.tool_permission_mode = "ask"
        self.tools = ToolRegistry()
        register_filesystem_tools(self.tools, config.workspace, confirm_outside=self._confirm_outside_workspace)
        register_search_tools(self.tools, config.workspace, confirm_outside=self._confirm_outside_workspace)
        register_patch_tools(self.tools, config.workspace, confirm_outside=self._confirm_outside_workspace)
        register_shell_tools(
            self.tools,
            config.workspace,
            confirm_exec=self._confirm_shell_exec,
            confirm_outside=self._confirm_outside_workspace,
        )
        self.runner = AgentRunner(self.provider)

    def set_tool_permission_mode(self, mode: str) -> None:
        normalized = mode.strip().lower()
        if normalized not in self.VALID_TOOL_PERMISSION_MODES:
            allowed = ", ".join(sorted(self.VALID_TOOL_PERMISSION_MODES))
            raise ValueError(f"Unknown permission mode {mode!r}; expected one of: {allowed}")
        self.tool_permission_mode = normalized

    def _confirm_outside_workspace(self, candidate: Path, workspace: Path, original_path: str) -> bool:
        if self.tool_permission_mode == "open":
            return True
        if self.tool_permission_mode == "strict":
            return False
        return confirm_outside_workspace(candidate, workspace, original_path)

    def _confirm_shell_exec(self, command: str, cwd: Path) -> bool:
        if self.tool_permission_mode == "open":
            return True
        if self.tool_permission_mode == "strict":
            return False
        return confirm_shell_exec(command, cwd)

    async def refresh_memory_summary(self, session: Session, *, force: bool = False) -> bool:
        cutoff = self._memory_summary_cutoff(session, force=force)
        if cutoff <= 0 or cutoff <= session.memory_summary_message_count:
            return False
        new_messages = session.messages[session.memory_summary_message_count : cutoff]
        if not new_messages:
            return False
        prompt = self._build_memory_prompt(session.memory_summary, new_messages)
        response = await self.provider.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You maintain durable memory for a personal assistant. "
                        "Summarize only stable facts, decisions, preferences, goals, and useful context. "
                        "Do not include transient chatter unless it matters later."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            tools=None,
            max_tokens=self.config.memory_summary_max_tokens,
            temperature=0.1,
        )
        summary = (response.content or "").strip()
        if not summary:
            return False
        session.set_memory_summary(summary, cutoff)
        return True

    def _memory_summary_cutoff(self, session: Session, *, force: bool) -> int:
        keep = max(0, self.config.memory_summary_keep_messages)
        total = len(session.messages)
        if total <= keep:
            return 0
        if not force and total < self.config.memory_summary_trigger_messages:
            return 0
        return max(0, total - keep)

    def _build_memory_prompt(self, existing_summary: str, messages: list[dict]) -> str:
        sections = [
            "Update the assistant memory summary using the existing summary and the new transcript.",
            "Return a concise bullet list or short paragraphs. Keep it factual and reusable.",
            "",
            "[Existing Summary]",
            existing_summary.strip() or "(none)",
            "[/Existing Summary]",
            "",
            "[New Transcript]",
        ]
        for message in messages:
            role = str(message.get("role") or "unknown")
            content = str(message.get("content") or "").strip()
            if not content:
                continue
            if len(content) > 2000:
                content = content[:1999].rstrip() + "..."
            sections.append(f"{role}: {content}")
        sections.append("[/New Transcript]")
        return "\n".join(sections)

    async def process(self, inbound: InboundMessage) -> OutboundMessage:
        session = self.sessions.get_or_create(inbound.session_key)
        history = session.get_context_history(self.config.max_history_messages)
        initial_messages = self.context.build_messages(history, inbound, session.memory_summary)
        result = await self.runner.run(
            initial_messages,
            tools=self.tools,
            max_iterations=self.config.max_iterations,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            tools_enabled=self.tools_enabled,
        )
        tool_events = [
            {
                "name": event.name,
                "arguments": event.arguments,
                "result_preview": event.result_preview,
                "duration_ms": event.duration_ms,
                "error": event.error,
            }
            for event in result.tool_events
        ]
        session.add_message("user", inbound.content)
        session.add_message(
            "assistant",
            result.final_content,
            tools_used=result.tools_used,
            tool_events=tool_events,
            trace=result.trace,
        )
        memory_refreshed = False
        memory_error: str | None = None
        try:
            memory_refreshed = await self.refresh_memory_summary(session)
        except Exception as exc:
            memory_error = str(exc)
        self.sessions.save(session)
        return OutboundMessage(
            channel=inbound.channel,
            chat_id=inbound.chat_id,
            content=result.final_content,
            metadata={
                "tools_used": result.tools_used,
                "tool_events": tool_events,
                "trace": result.trace,
                "memory_refreshed": memory_refreshed,
                "memory_summary_message_count": session.memory_summary_message_count,
                "memory_error": memory_error,
            },
        )

    async def serve_forever(self) -> None:
        while True:
            inbound = await self.bus.consume_inbound()
            outbound = await self.process(inbound)
            await self.bus.publish_outbound(outbound)
