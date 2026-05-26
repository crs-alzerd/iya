from iya_bot.config import Settings, effective_timezone, is_owner


def _settings(**overrides: object) -> Settings:
    data = {
        "TELEGRAM_BOT_TOKEN": "token",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/db",
        "LLM_BASE_URL": "https://example.test/v1",
        "LLM_API_KEY": "key",
        "LLM_MODEL": "model",
        "OWNER_TELEGRAM_ID": "",
        "BOT_TIMEZONE": "",
    }
    data.update(overrides)
    return Settings(**data)


def test_empty_owner_id_is_treated_as_not_configured() -> None:
    settings = _settings()

    assert settings.owner_telegram_id is None
    assert not is_owner(123, settings)


def test_owner_check() -> None:
    settings = _settings(OWNER_TELEGRAM_ID="123")

    assert is_owner(123, settings)
    assert not is_owner(456, settings)


def test_effective_timezone_prefers_bot_timezone() -> None:
    settings = _settings(TZ="Europe/Paris", BOT_TIMEZONE="Europe/Moscow")

    assert effective_timezone(settings) == "Europe/Moscow"
