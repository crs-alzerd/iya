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

    owner_telegram_id: int | None = Field(default=None, alias="OWNER_TELEGRAM_ID")
    app_env: str = Field(default="production", alias="APP_ENV")
    app_version: str = Field(default="0.1.1", alias="APP_VERSION")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    timezone: str = Field(default="Europe/Moscow", alias="TZ")
    bot_timezone: str | None = Field(default=None, alias="BOT_TIMEZONE")
    history_limit: int = Field(default=20, alias="HISTORY_LIMIT")
    system_prompt_path: str = Field(default="/app/prompts/iya_system.md", alias="SYSTEM_PROMPT_PATH")
    reminder_scan_interval_seconds: int = Field(default=10, alias="REMINDER_SCAN_INTERVAL_SECONDS")


    @field_validator("owner_telegram_id", mode="before")
    @classmethod
    def _empty_owner_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator("bot_timezone", mode="before")
    @classmethod
    def _empty_bot_timezone_to_none(cls, value: object) -> object:
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
