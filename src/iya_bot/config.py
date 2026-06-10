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
    # Приватный режим: список telegram id через запятую. Пусто — бот открыт всем.
    # Владелец имеет доступ всегда, даже если его нет в списке.
    allowed_telegram_ids: str = Field(default="", alias="ALLOWED_TELEGRAM_IDS")
    app_env: str = Field(default="production", alias="APP_ENV")
    app_version: str = Field(default="0.4.0-manifest-v2", alias="APP_VERSION")

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

    # Rate limiting: не больше N сообщений в окно на пользователя. Владелец не ограничен.
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_messages: int = Field(default=20, alias="RATE_LIMIT_MESSAGES")
    rate_limit_window_seconds: int = Field(default=60, alias="RATE_LIMIT_WINDOW_SECONDS")

    # Голосовые сообщения через Whisper-совместимый endpoint (/audio/transcriptions).
    # Пустые base_url/api_key/model — наследуются от основного LLM-подключения.
    voice_enabled: bool = Field(default=False, alias="VOICE_ENABLED")
    whisper_base_url: str | None = Field(default=None, alias="WHISPER_BASE_URL")
    whisper_api_key: SecretStr | None = Field(default=None, alias="WHISPER_API_KEY")
    whisper_model: str = Field(default="whisper-1", alias="WHISPER_MODEL")
    telegram_voice_max_bytes: int = Field(default=10_000_000, alias="TELEGRAM_VOICE_MAX_BYTES")

    # Streaming: ответ редактируется в одном Telegram-сообщении по мере генерации.
    # Работает только на прямом текстовом пути (без tool-loop и vision).
    streaming_enabled: bool = Field(default=False, alias="STREAMING_ENABLED")
    streaming_edit_interval_seconds: float = Field(default=1.5, alias="STREAMING_EDIT_INTERVAL_SECONDS")

    # Семантический поиск по памяти: эмбеддинги фактов + косинусное ранжирование.
    # Эмбеддинги хранятся в JSON-колонке, ранжирование в Python — pgvector не нужен.
    memory_embeddings_enabled: bool = Field(default=False, alias="MEMORY_EMBEDDINGS_ENABLED")
    embeddings_base_url: str | None = Field(default=None, alias="EMBEDDINGS_BASE_URL")
    embeddings_api_key: SecretStr | None = Field(default=None, alias="EMBEDDINGS_API_KEY")
    embeddings_model: str = Field(default="text-embedding-3-small", alias="EMBEDDINGS_MODEL")
    memory_retrieval_top_k: int = Field(default=20, alias="MEMORY_RETRIEVAL_TOP_K")

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
        "whisper_base_url",
        "whisper_api_key",
        "embeddings_base_url",
        "embeddings_api_key",
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


def parse_allowed_ids(raw: str) -> frozenset[int]:
    ids: set[int] = set()
    for part in raw.replace(",", " ").split():
        try:
            ids.add(int(part))
        except ValueError:
            continue
    return frozenset(ids)


def is_allowed(user_id: int | None, settings: Settings | None = None) -> bool:
    if user_id is None:
        return False
    current_settings = settings or get_settings()
    if is_owner(user_id, current_settings):
        return True
    allowed = parse_allowed_ids(current_settings.allowed_telegram_ids)
    if not allowed:
        return True
    return user_id in allowed


def effective_timezone(settings: Settings | None = None) -> str:
    current_settings = settings or get_settings()
    return current_settings.bot_timezone or current_settings.timezone
