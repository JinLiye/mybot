"""Main orchestration loop for mybot."""

from __future__ import annotations

from mybot.bus import MessageBus
from mybot.config import BotConfig
from mybot.context import ContextBuilder
from mybot.events import InboundMessage, OutboundMessage
from mybot.providers.openai_compat import OpenAICompatProvider
from mybot.runner import AgentRunner
from mybot.session import SessionStore
from mybot.tools.filesystem import register_filesystem_tools
from mybot.tools.registry import ToolRegistry


class AgentLoop:
    """Small orchestrator inspired by nanobot's layering."""

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
        self.tools = ToolRegistry()
        register_filesystem_tools(self.tools, config.workspace)
        self.runner = AgentRunner(self.provider)

    async def process(self, inbound: InboundMessage) -> OutboundMessage:
        session = self.sessions.get_or_create(inbound.session_key)
        history = session.get_history(self.config.max_history_messages)
        initial_messages = self.context.build_messages(history, inbound)
        result = await self.runner.run(
            initial_messages,
            tools=self.tools,
            max_iterations=self.config.max_iterations,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
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
        )
        self.sessions.save(session)
        return OutboundMessage(
            channel=inbound.channel,
            chat_id=inbound.chat_id,
            content=result.final_content,
            metadata={"tools_used": result.tools_used, "tool_events": tool_events},
        )

    async def serve_forever(self) -> None:
        while True:
            inbound = await self.bus.consume_inbound()
            outbound = await self.process(inbound)
            await self.bus.publish_outbound(outbound)
