from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_bot_token: SecretStr = Field(alias="TELEGRAM_BOT_TOKEN")

    database_url: str = Field(alias="DATABASE_URL")

    llm_base_url: str = Field(alias="LLM_BASE_URL")
    llm_api_key: SecretStr = Field(alias="LLM_API_KEY")
    llm_model: str = Field(alias="LLM_MODEL")
    llm_timeout_seconds: int = Field(default=60, alias="LLM_TIMEOUT_SECONDS")

<<<<<<< HEAD
    owner_telegram_id: int | None = Field(default=None, alias="OWNER_TELEGRAM_ID")
    app_env: str = Field(default="production", alias="APP_ENV")
    app_version: str = Field(default="0.1.1", alias="APP_VERSION")
=======
    # Сэмплинг. presence/frequency penalty — главный рычаг против
    # дословных повторов и зацикливания на одних и тех же жестах.
    llm_temperature: float = Field(default=0.85, alias="LLM_TEMPERATURE")
    llm_top_p: float | None = Field(default=None, alias="LLM_TOP_P")
    llm_presence_penalty: float | None = Field(default=0.4, alias="LLM_PRESENCE_PENALTY")
    llm_frequency_penalty: float | None = Field(default=0.5, alias="LLM_FREQUENCY_PENALTY")
    llm_max_tokens: int | None = Field(default=None, alias="LLM_MAX_TOKENS")

    owner_telegram_id: int | None = Field(default=None, alias="OWNER_TELEGRAM_ID")
    app_env: str = Field(default="production", alias="APP_ENV")
    app_version: str = Field(default="0.2.0", alias="APP_VERSION")
>>>>>>> 1917e25 (Rebuilt full)

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    timezone: str = Field(default="Europe/Moscow", alias="TZ")
    bot_timezone: str | None = Field(default=None, alias="BOT_TIMEZONE")
    history_limit: int = Field(default=20, alias="HISTORY_LIMIT")
    system_prompt_path: str = Field(default="/app/prompts/iya_system.md", alias="SYSTEM_PROMPT_PATH")
<<<<<<< HEAD
=======

    # «Человеческая» подача: дробление ответа на несколько реплик с
    # имитацией набора текста, как пишет живой собеседник в Telegram.
    humanize_enabled: bool = Field(default=True, alias="HUMANIZE_ENABLED")
    humanize_max_chunks: int = Field(default=3, alias="HUMANIZE_MAX_CHUNKS")
    humanize_ms_per_char: int = Field(default=22, alias="HUMANIZE_MS_PER_CHAR")
    humanize_min_delay_seconds: float = Field(default=0.6, alias="HUMANIZE_MIN_DELAY_SECONDS")
    humanize_max_delay_seconds: float = Field(default=4.0, alias="HUMANIZE_MAX_DELAY_SECONDS")

    # Динамический контекст: текущее время/день недели и анти-повтор —
    # подмешиваются в каждый запрос отдельным system-блоком.
    runtime_context_enabled: bool = Field(default=True, alias="RUNTIME_CONTEXT_ENABLED")
>>>>>>> 1917e25 (Rebuilt full)
    reminder_scan_interval_seconds: int = Field(default=10, alias="REMINDER_SCAN_INTERVAL_SECONDS")
    proactive_enabled: bool = Field(default=True, alias="PROACTIVE_ENABLED")
    proactive_scan_interval_seconds: int = Field(default=60, alias="PROACTIVE_SCAN_INTERVAL_SECONDS")
    proactive_min_delay_minutes: int = Field(default=180, alias="PROACTIVE_MIN_DELAY_MINUTES")
    proactive_max_delay_minutes: int = Field(default=720, alias="PROACTIVE_MAX_DELAY_MINUTES")
    reflection_enabled: bool = Field(default=True, alias="REFLECTION_ENABLED")
    reflection_interval_minutes: int = Field(default=360, alias="REFLECTION_INTERVAL_MINUTES")
    reflection_user_limit: int = Field(default=20, alias="REFLECTION_USER_LIMIT")
    reflection_keep_recent_messages: int = Field(default=200, alias="REFLECTION_KEEP_RECENT_MESSAGES")
    telegram_image_max_bytes: int = Field(default=5_000_000, alias="TELEGRAM_IMAGE_MAX_BYTES")

    @field_validator("owner_telegram_id", mode="before")
    @classmethod
    def _empty_owner_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

<<<<<<< HEAD
    @field_validator("bot_timezone", mode="before")
    @classmethod
    def _empty_bot_timezone_to_none(cls, value: object) -> object:
=======
    @field_validator(
        "llm_top_p",
        "llm_max_tokens",
        "bot_timezone",
        mode="before",
    )
    @classmethod
    def _empty_optional_to_none(cls, value: object) -> object:
>>>>>>> 1917e25 (Rebuilt full)
        if value == "":
            return None
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def is_owner(user_id: int | None, settings: Settings | None = None) -> bool:
    if user_id is None:
        return False
    current_settings = settings or get_settings()
    if current_settings.owner_telegram_id is None:
        return False
    return user_id == current_settings.owner_telegram_id


def effective_timezone(settings: Settings | None = None) -> str:
    current_settings = settings or get_settings()
    return current_settings.bot_timezone or current_settings.timezone
