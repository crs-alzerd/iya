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


def test_sampling_defaults_enable_anti_repetition_penalties() -> None:
    settings = _settings()

    assert settings.llm_presence_penalty == 0.4
    assert settings.llm_frequency_penalty == 0.5
    assert settings.llm_temperature == 0.85


def test_optional_sampling_params_default_to_none() -> None:
    settings = _settings(LLM_TOP_P="", LLM_MAX_TOKENS="")

    assert settings.llm_top_p is None
    assert settings.llm_max_tokens is None


def test_humanize_defaults() -> None:
    settings = _settings()

    assert settings.humanize_enabled is True
    assert settings.humanize_max_chunks == 3
    assert settings.runtime_context_enabled is True
