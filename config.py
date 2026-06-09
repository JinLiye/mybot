"""Configuration helpers for mybot."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path | None = None) -> None:
    """Load simple KEY=VALUE lines into os.environ without overriding real env vars."""
    env_path = path or Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped if stripped else default


@dataclass(slots=True)
class ProviderConfig:
    name: str
    api_key: str
    api_base: str
    model: str


@dataclass(slots=True)
class BotConfig:
    provider: ProviderConfig
    workspace: Path
    session_dir: Path
    system_prompt: str
    max_history_messages: int = 20
    max_iterations: int = 4
    max_tokens: int = 2048
    temperature: float = 0.2
    memory_summary_trigger_messages: int = 24
    memory_summary_keep_messages: int = 12
    memory_summary_max_tokens: int = 512

    @classmethod
    def from_env(cls) -> "BotConfig":
        load_dotenv()
        provider_name = (_env("MYBOT_PROVIDER", "vllm") or "vllm").lower()
        workspace = Path(_env("MYBOT_WORKSPACE", str(Path.cwd())) or ".").expanduser().resolve()
        session_dir = Path(
            _env("MYBOT_SESSION_DIR", str(workspace / ".data" / "sessions")) or workspace / ".data" / "sessions"
        ).expanduser()

        if provider_name == "bailian":
            provider = ProviderConfig(
                name="bailian",
                api_key=_env("MYBOT_BAILIAN_API_KEY", "") or "",
                api_base=(
                    _env("MYBOT_BAILIAN_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
                    or "https://dashscope.aliyuncs.com/compatible-mode/v1"
                ),
                model=_env("MYBOT_BAILIAN_MODEL", "qwen-plus-latest") or "qwen-plus-latest",
            )
        else:
            provider = ProviderConfig(
                name="vllm",
                api_key=_env("MYBOT_VLLM_API_KEY", "EMPTY") or "EMPTY",
                api_base=_env("MYBOT_VLLM_API_BASE", "http://127.0.0.1:8000/v1") or "http://127.0.0.1:8000/v1",
                model=_env("MYBOT_VLLM_MODEL", "Qwen/Qwen3-8B") or "Qwen/Qwen3-8B",
            )

        system_prompt = _env(
            "MYBOT_SYSTEM_PROMPT",
            (
                "You are mybot, a pragmatic AI assistant. "
                "Answer clearly, use tools when needed, and keep track of ongoing context."
            ),
        ) or ""
        max_history_messages = int(_env("MYBOT_MAX_HISTORY_MESSAGES", "20") or "20")
        max_iterations = int(_env("MYBOT_MAX_ITERATIONS", "4") or "4")
        max_tokens = int(_env("MYBOT_MAX_TOKENS", "2048") or "2048")
        temperature = float(_env("MYBOT_TEMPERATURE", "0.2") or "0.2")
        memory_summary_trigger_messages = int(_env("MYBOT_MEMORY_SUMMARY_TRIGGER_MESSAGES", "24") or "24")
        memory_summary_keep_messages = int(_env("MYBOT_MEMORY_SUMMARY_KEEP_MESSAGES", "12") or "12")
        memory_summary_max_tokens = int(_env("MYBOT_MEMORY_SUMMARY_MAX_TOKENS", "512") or "512")

        return cls(
            provider=provider,
            workspace=workspace,
            session_dir=session_dir,
            system_prompt=system_prompt,
            max_history_messages=max_history_messages,
            max_iterations=max_iterations,
            max_tokens=max_tokens,
            temperature=temperature,
            memory_summary_trigger_messages=memory_summary_trigger_messages,
            memory_summary_keep_messages=memory_summary_keep_messages,
            memory_summary_max_tokens=memory_summary_max_tokens,
        )
