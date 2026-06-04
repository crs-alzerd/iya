import asyncio
import logging

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from iya_bot.application.dialogue import DialogueService
from iya_bot.application.proactive import ProactiveService
from iya_bot.application.reflection import ReflectionService
from iya_bot.application.reminders import ReminderService
from iya_bot.config import effective_timezone, get_settings
from iya_bot.infrastructure.db.repositories import (
    ProactiveEventDueRepository,
    ReminderDueRepository,
    SqlAlchemyProactiveEventRepository,
    SqlAlchemyMemoryRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyReminderRepository,
    SqlAlchemyUserRepository,
)
from iya_bot.infrastructure.db.session import create_engine, create_session_factory
from iya_bot.infrastructure.llm.openai_compatible import OpenAICompatibleClient
from iya_bot.infrastructure.scheduler.proactive_jobs import ProactiveJobRunner
from iya_bot.infrastructure.scheduler.reflection_jobs import ReflectionJobRunner
from iya_bot.infrastructure.scheduler.reminder_jobs import ReminderJobRunner
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
    reminder_repo = SqlAlchemyReminderRepository(session_factory)
    reminder_due_repo = ReminderDueRepository(session_factory)
    proactive_repo = SqlAlchemyProactiveEventRepository(session_factory)
    proactive_due_repo = ProactiveEventDueRepository(session_factory)

    llm = OpenAICompatibleClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key.get_secret_value(),
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )

    dialogue = DialogueService(
        users=users,
        messages=messages,
        memories=memories,
        llm=llm,
        history_limit=settings.history_limit,
        system_prompt_path=settings.system_prompt_path,
    )
    reminder_service = ReminderService(reminder_repo)
    proactive_service = ProactiveService(
        events=proactive_repo,
        messages=messages,
        memories=memories,
        llm=llm,
        history_limit=settings.history_limit,
        min_delay_minutes=settings.proactive_min_delay_minutes,
        max_delay_minutes=settings.proactive_max_delay_minutes,
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
            reminders=reminder_service,
            proactive=proactive_service if settings.proactive_enabled else None,
            reflection=reflection_service if settings.reflection_enabled else None,
            session_factory=session_factory,
            settings=settings,
        )
    )

    reminder_jobs = ReminderJobRunner(bot=bot, repository=reminder_due_repo)
    proactive_jobs = ProactiveJobRunner(
        bot=bot,
        due_repository=proactive_due_repo,
        proactive=proactive_service,
    )
    reflection_jobs = ReflectionJobRunner(
        reflection=reflection_service,
        user_limit=settings.reflection_user_limit,
    )
    scheduler = AsyncIOScheduler(timezone=effective_timezone(settings))
    scheduler.add_job(
        reminder_jobs.send_due_reminders,
        "interval",
        seconds=settings.reminder_scan_interval_seconds,
        max_instances=1,
        coalesce=True,
    )
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
    scheduler.start()

    logger.info("Iya Next Clean starting polling. env=%s version=%s prompt=%s", settings.app_env, settings.app_version, settings.system_prompt_path)
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
