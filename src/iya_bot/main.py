import asyncio
import logging

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from iya_bot.application.dialogue import DialogueService
from iya_bot.application.llm_router import LLMRouter
from iya_bot.application.memory_control import MemoryControlService
from iya_bot.application.memory_retrieval import MemoryRetrievalService
from iya_bot.application.mode_router import ModeRouter
from iya_bot.application.proactive import ProactiveService
from iya_bot.application.rate_limit import SlidingWindowRateLimiter
from iya_bot.application.reflection import ReflectionService
from iya_bot.application.self_state import SelfStateService
from iya_bot.application.tools import ToolRegistry
from iya_bot.application.tools.memory import RememberFactTool
from iya_bot.application.tools.web import FetchUrlTool, WebSearchTool
from iya_bot.config import effective_timezone, get_settings
from iya_bot.infrastructure.db.repositories import (
    ProactiveEventDueRepository,
    SqlAlchemyLLMRequestRepository,
    SqlAlchemyMemoryRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyProactiveEventRepository,
    SqlAlchemyRelationshipStateRepository,
    SqlAlchemySelfStateRepository,
    SqlAlchemyUserRepository,
)
from iya_bot.infrastructure.db.session import create_engine, create_session_factory
from iya_bot.infrastructure.llm.embeddings import OpenAICompatibleEmbeddingClient
from iya_bot.infrastructure.llm.openai_compatible import LLMSamplingParams, OpenAICompatibleClient
from iya_bot.infrastructure.llm.whisper import WhisperCompatibleTranscriber
from iya_bot.infrastructure.search.duckduckgo import DuckDuckGoSearchClient
from iya_bot.infrastructure.search.http_fetcher import HttpPageFetcher
from iya_bot.infrastructure.scheduler.proactive_jobs import ProactiveJobRunner
from iya_bot.infrastructure.scheduler.reflection_jobs import ReflectionJobRunner
from iya_bot.infrastructure.telegram.handlers import build_router


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logger = logging.getLogger("iya_bot")

    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    users = SqlAlchemyUserRepository(session_factory)
    messages = SqlAlchemyMessageRepository(session_factory)
    memories = SqlAlchemyMemoryRepository(session_factory)
    proactive_repo = SqlAlchemyProactiveEventRepository(session_factory)
    proactive_due_repo = ProactiveEventDueRepository(session_factory)
    self_states = SqlAlchemySelfStateRepository(session_factory)
    relationships = SqlAlchemyRelationshipStateRepository(session_factory)
    llm_logs = SqlAlchemyLLMRequestRepository(session_factory) if settings.llm_logging_enabled else None

    llm_base = OpenAICompatibleClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key.get_secret_value(),
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        sampling=LLMSamplingParams(
            temperature=settings.llm_temperature,
            top_p=settings.llm_top_p,
            presence_penalty=settings.llm_presence_penalty,
            frequency_penalty=settings.llm_frequency_penalty,
            max_tokens=settings.llm_max_tokens,
        ),
    )
    llm = LLMRouter(
        llm_base,
        provider=settings.llm_provider_name,
        model=settings.llm_model,
        request_logs=llm_logs,
    )

    mode_router = ModeRouter() if settings.mode_router_enabled else None
    self_state_service = (
        SelfStateService(
            states=self_states,
            relationships=relationships if settings.relationship_state_enabled else None,
        )
        if settings.self_state_enabled
        else None
    )
    memory_control = MemoryControlService(
        memories=memories,
        self_states=self_states if settings.self_state_enabled else None,
        relationships=relationships if settings.relationship_state_enabled else None,
    )

    tools: ToolRegistry | None = None
    if settings.tools_enabled:
        tool_list = []
        if settings.web_search_enabled:
            tool_list.append(
                WebSearchTool(
                    DuckDuckGoSearchClient(timeout_seconds=settings.web_search_timeout_seconds),
                    max_results=settings.web_search_max_results,
                )
            )
        if settings.fetch_url_enabled:
            tool_list.append(
                FetchUrlTool(
                    HttpPageFetcher(timeout_seconds=settings.fetch_url_timeout_seconds),
                    max_chars=settings.fetch_url_max_chars,
                )
            )
        if settings.remember_tool_enabled:
            tool_list.append(RememberFactTool(memories))
        if tool_list:
            tools = ToolRegistry(tool_list)

    transcriber: WhisperCompatibleTranscriber | None = None
    if settings.voice_enabled:
        transcriber = WhisperCompatibleTranscriber(
            base_url=settings.whisper_base_url or settings.llm_base_url,
            api_key=(
                settings.whisper_api_key.get_secret_value()
                if settings.whisper_api_key is not None
                else settings.llm_api_key.get_secret_value()
            ),
            model=settings.whisper_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    embedder: OpenAICompatibleEmbeddingClient | None = None
    memory_retrieval: MemoryRetrievalService | None = None
    if settings.memory_embeddings_enabled:
        embedder = OpenAICompatibleEmbeddingClient(
            base_url=settings.embeddings_base_url or settings.llm_base_url,
            api_key=(
                settings.embeddings_api_key.get_secret_value()
                if settings.embeddings_api_key is not None
                else settings.llm_api_key.get_secret_value()
            ),
            model=settings.embeddings_model,
        )
        memory_retrieval = MemoryRetrievalService(
            embedder=embedder,
            memories=memories,
            top_k=settings.memory_retrieval_top_k,
        )

    rate_limiter = (
        SlidingWindowRateLimiter(
            max_events=settings.rate_limit_messages,
            window_seconds=settings.rate_limit_window_seconds,
        )
        if settings.rate_limit_enabled
        else None
    )

    dialogue = DialogueService(
        users=users,
        messages=messages,
        memories=memories,
        llm=llm,
        history_limit=settings.history_limit,
        system_prompt_path=settings.system_prompt_path,
        runtime_context_enabled=settings.runtime_context_enabled,
        timezone_name=effective_timezone(settings),
        mode_router=mode_router,
        self_state=self_state_service,
        prompt_token_budget=settings.prompt_token_budget,
        prompt_builder_v2_enabled=settings.prompt_builder_v2_enabled,
        tools=tools,
        tool_max_iterations=settings.tool_max_iterations,
        auto_memory_enabled=settings.auto_memory_enabled,
        auto_memory_max_facts=settings.auto_memory_max_facts,
        memory_retrieval=memory_retrieval,
    )
    proactive_service = ProactiveService(
        events=proactive_repo,
        messages=messages,
        memories=memories,
        llm=llm,
        history_limit=settings.history_limit,
        min_delay_minutes=settings.proactive_min_delay_minutes,
        max_delay_minutes=settings.proactive_max_delay_minutes,
        timezone_name=effective_timezone(settings),
        runtime_context_enabled=settings.runtime_context_enabled,
    )
    reflection_service = ReflectionService(
        users=users,
        messages=messages,
        memories=memories,
        llm=llm,
        keep_recent_messages=settings.reflection_keep_recent_messages,
    )

    bot = Bot(token=settings.telegram_bot_token.get_secret_value())
    dispatcher = Dispatcher()
    dispatcher.include_router(
        build_router(
            dialogue=dialogue,
            proactive=proactive_service if settings.proactive_enabled else None,
            reflection=reflection_service if settings.reflection_enabled else None,
            memory_control=memory_control,
            session_factory=session_factory,
            settings=settings,
            rate_limiter=rate_limiter,
            transcriber=transcriber,
        )
    )

    proactive_jobs = ProactiveJobRunner(bot=bot, due_repository=proactive_due_repo, proactive=proactive_service)
    reflection_jobs = ReflectionJobRunner(reflection=reflection_service, user_limit=settings.reflection_user_limit)
    scheduler = AsyncIOScheduler(timezone=effective_timezone(settings))
    if settings.proactive_enabled:
        scheduler.add_job(
            proactive_jobs.send_due_events,
            "interval",
            seconds=settings.proactive_scan_interval_seconds,
            max_instances=1,
            coalesce=True,
        )
    if settings.reflection_enabled:
        scheduler.add_job(
            reflection_jobs.reflect_memories,
            "interval",
            minutes=settings.reflection_interval_minutes,
            max_instances=1,
            coalesce=True,
        )
    if rate_limiter is not None:
        scheduler.add_job(rate_limiter.prune, "interval", minutes=30, max_instances=1, coalesce=True)
    scheduler.start()

    logger.info(
        "Iya starting polling. env=%s version=%s prompt=%s manifest_v2=%s",
        settings.app_env,
        settings.app_version,
        settings.system_prompt_path,
        settings.prompt_builder_v2_enabled,
    )
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await dialogue.drain_background_tasks()
        await llm_base.aclose()
        if transcriber is not None:
            await transcriber.aclose()
        if embedder is not None:
            await embedder.aclose()
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
