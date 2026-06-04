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
