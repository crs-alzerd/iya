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
    llm_provider_name: str = Field(default="openai-compatible", alias="LLM_PROVIDER_NAME")

    llm_temperature: float = Field(default=0.85, alias="LLM_TEMPERATURE")
    llm_top_p: float | None = Field(default=None, alias="LLM_TOP_P")
    llm_presence_penalty: float | None = Field(default=0.4, alias="LLM_PRESENCE_PENALTY")
    llm_frequency_penalty: float | None = Field(default=0.5, alias="LLM_FREQUENCY_PENALTY")
    llm_max_tokens: int | None = Field(default=None, alias="LLM_MAX_TOKENS")

    owner_telegram_id: int | None = Field(default=None, alias="OWNER_TELEGRAM_ID")
    app_env: str = Field(default="production", alias="APP_ENV")
    app_version: str = Field(default="0.3.0-manifest-v2", alias="APP_VERSION")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    timezone: str = Field(default="Europe/Moscow", alias="TZ")
    bot_timezone: str | None = Field(default=None, alias="BOT_TIMEZONE")
    history_limit: int = Field(default=20, alias="HISTORY_LIMIT")
    system_prompt_path: str = Field(default="/app/prompts/iya_system.md", alias="SYSTEM_PROMPT_PATH")

    humanize_enabled: bool = Field(default=True, alias="HUMANIZE_ENABLED")
    humanize_max_chunks: int = Field(default=2, alias="HUMANIZE_MAX_CHUNKS")
    humanize_ms_per_char: int = Field(default=22, alias="HUMANIZE_MS_PER_CHAR")
    humanize_min_delay_seconds: float = Field(default=0.6, alias="HUMANIZE_MIN_DELAY_SECONDS")
    humanize_max_delay_seconds: float = Field(default=4.0, alias="HUMANIZE_MAX_DELAY_SECONDS")

    runtime_context_enabled: bool = Field(default=True, alias="RUNTIME_CONTEXT_ENABLED")
    proactive_enabled: bool = Field(default=True, alias="PROACTIVE_ENABLED")
    proactive_scan_interval_seconds: int = Field(default=60, alias="PROACTIVE_SCAN_INTERVAL_SECONDS")
    proactive_min_delay_minutes: int = Field(default=180, alias="PROACTIVE_MIN_DELAY_MINUTES")
    proactive_max_delay_minutes: int = Field(default=720, alias="PROACTIVE_MAX_DELAY_MINUTES")
    reflection_enabled: bool = Field(default=True, alias="REFLECTION_ENABLED")
    reflection_interval_minutes: int = Field(default=360, alias="REFLECTION_INTERVAL_MINUTES")
    reflection_user_limit: int = Field(default=20, alias="REFLECTION_USER_LIMIT")
    reflection_keep_recent_messages: int = Field(default=200, alias="REFLECTION_KEEP_RECENT_MESSAGES")
    telegram_image_max_bytes: int = Field(default=5_000_000, alias="TELEGRAM_IMAGE_MAX_BYTES")
    vision_enabled: bool = Field(default=True, alias="VISION_ENABLED")

    # Manifest v2 feature flags. Keep them explicit to allow staged rollout on VPS.
    memory_facts_enabled: bool = Field(default=True, alias="MEMORY_FACTS_ENABLED")
    self_state_enabled: bool = Field(default=True, alias="SELF_STATE_ENABLED")
    relationship_state_enabled: bool = Field(default=True, alias="RELATIONSHIP_STATE_ENABLED")
    mode_router_enabled: bool = Field(default=True, alias="MODE_ROUTER_ENABLED")
    prompt_builder_v2_enabled: bool = Field(default=True, alias="PROMPT_BUILDER_V2_ENABLED")
    llm_logging_enabled: bool = Field(default=True, alias="LLM_LOGGING_ENABLED")
    motivated_proactive_enabled: bool = Field(default=False, alias="MOTIVATED_PROACTIVE_ENABLED")
    prompt_token_budget: int = Field(default=12_000, alias="PROMPT_TOKEN_BUDGET")

    # Tool-calling (function calling). Инструменты, которые Ия может вызывать сама.
    tools_enabled: bool = Field(default=True, alias="TOOLS_ENABLED")
    tool_max_iterations: int = Field(default=4, alias="TOOL_MAX_ITERATIONS")
    web_search_enabled: bool = Field(default=True, alias="WEB_SEARCH_ENABLED")
    web_search_max_results: int = Field(default=5, alias="WEB_SEARCH_MAX_RESULTS")
    web_search_timeout_seconds: int = Field(default=15, alias="WEB_SEARCH_TIMEOUT_SECONDS")
    fetch_url_enabled: bool = Field(default=True, alias="FETCH_URL_ENABLED")
    fetch_url_max_chars: int = Field(default=4000, alias="FETCH_URL_MAX_CHARS")
    fetch_url_timeout_seconds: int = Field(default=15, alias="FETCH_URL_TIMEOUT_SECONDS")
    remember_tool_enabled: bool = Field(default=True, alias="REMEMBER_TOOL_ENABLED")

    # Пассивное авто-запоминание фактов из диалога.
    auto_memory_enabled: bool = Field(default=True, alias="AUTO_MEMORY_ENABLED")
    auto_memory_max_facts: int = Field(default=5, alias="AUTO_MEMORY_MAX_FACTS")

    @field_validator("owner_telegram_id", mode="before")
    @classmethod
    def _empty_owner_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator(
        "llm_top_p",
        "llm_max_tokens",
        "bot_timezone",
        mode="before",
    )
    @classmethod
    def _empty_optional_to_none(cls, value: object) -> object:
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
