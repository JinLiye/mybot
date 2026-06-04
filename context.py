"""Prompt and message assembly for mybot."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from mybot.events import InboundMessage


class ContextBuilder:
    """Build the model-visible message chain."""

    def __init__(self, system_prompt: str) -> None:
        self.system_prompt = system_prompt

    def build_messages(
        self,
        history: list[dict[str, Any]],
        inbound: InboundMessage,
    ) -> list[dict[str, Any]]:
        runtime_note = self._runtime_note(inbound)
        user_content = f"{inbound.content}\n\n{runtime_note}"
        return [
            {"role": "system", "content": self.system_prompt},
            *history,
            {"role": "user", "content": user_content},
        ]

    @staticmethod
    def _runtime_note(inbound: InboundMessage) -> str:
        ts = inbound.timestamp.isoformat(timespec="seconds")
        lines = [
            "[Runtime Context]",
            f"Current Time: {datetime.now().isoformat(timespec='seconds')}",
            f"Message Time: {ts}",
            f"Channel: {inbound.channel}",
            f"Chat ID: {inbound.chat_id}",
            f"Sender ID: {inbound.sender_id}",
            "[/Runtime Context]",
        ]
        return "\n".join(lines)
