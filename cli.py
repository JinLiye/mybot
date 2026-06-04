"""CLI entrypoint for mybot."""

from __future__ import annotations

import argparse
import asyncio
from uuid import uuid4

from mybot.config import BotConfig
from mybot.events import InboundMessage
from mybot.loop import AgentLoop


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
    chat_id = str(uuid4())

    print(f"mybot provider={config.provider.name} model={config.provider.model}")
    print("Type 'exit' or 'quit' to stop.")

    while True:
        user_text = input("you> ").strip()
        if user_text.lower() in {"exit", "quit"}:
            break
        inbound = InboundMessage(
            channel="cli",
            sender_id="local-user",
            chat_id=chat_id,
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
