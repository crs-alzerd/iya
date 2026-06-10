from iya_bot.config import Settings, effective_timezone, is_allowed, is_owner, parse_allowed_ids


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
    # _env_file=None: юнит-тесты не должны зависеть от локального .env разработчика.
    return Settings(_env_file=None, **data)


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
    assert settings.humanize_max_chunks == 2
    assert settings.runtime_context_enabled is True


def test_parse_allowed_ids_tolerates_commas_spaces_and_junk() -> None:
    assert parse_allowed_ids("") == frozenset()
    assert parse_allowed_ids("1, 2,3") == frozenset({1, 2, 3})
    assert parse_allowed_ids(" 7  8 ") == frozenset({7, 8})
    assert parse_allowed_ids("9, oops, 10") == frozenset({9, 10})


def test_empty_allowlist_means_open_access() -> None:
    settings = _settings()

    assert is_allowed(123, settings)
    assert not is_allowed(None, settings)


def test_allowlist_restricts_access() -> None:
    settings = _settings(ALLOWED_TELEGRAM_IDS="100, 200")

    assert is_allowed(100, settings)
    assert is_allowed(200, settings)
    assert not is_allowed(300, settings)


def test_owner_always_allowed_even_outside_allowlist() -> None:
    settings = _settings(OWNER_TELEGRAM_ID="42", ALLOWED_TELEGRAM_IDS="100")

    assert is_allowed(42, settings)
