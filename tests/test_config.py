from config import BotConfig


def test_from_env_defaults_to_vllm(monkeypatch) -> None:
    monkeypatch.delenv("MYBOT_PROVIDER", raising=False)
    config = BotConfig.from_env()

    assert config.provider.name == "vllm"
    assert config.provider.api_base == "http://127.0.0.1:8000/v1"


def test_from_env_supports_bailian(monkeypatch) -> None:
    monkeypatch.setenv("MYBOT_PROVIDER", "bailian")
    monkeypatch.setenv("MYBOT_BAILIAN_API_KEY", "test-key")
    config = BotConfig.from_env()

    assert config.provider.name == "bailian"
    assert config.provider.api_key == "test-key"



def test_from_env_supports_memory_summary_config(monkeypatch) -> None:
    monkeypatch.setenv("MYBOT_MEMORY_SUMMARY_TRIGGER_MESSAGES", "8")
    monkeypatch.setenv("MYBOT_MEMORY_SUMMARY_KEEP_MESSAGES", "4")
    monkeypatch.setenv("MYBOT_MEMORY_SUMMARY_MAX_TOKENS", "256")

    config = BotConfig.from_env()

    assert config.memory_summary_trigger_messages == 8
    assert config.memory_summary_keep_messages == 4
    assert config.memory_summary_max_tokens == 256
