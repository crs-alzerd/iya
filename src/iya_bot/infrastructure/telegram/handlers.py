import logging
from base64 import b64encode
from io import BytesIO

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from iya_bot.application.dialogue import DialogueService
from iya_bot.application.proactive import ProactiveService
from iya_bot.application.reflection import ReflectionService
from iya_bot.application.reminders import ReminderParseError, ReminderService
from iya_bot.config import Settings, effective_timezone, is_owner

logger = logging.getLogger(__name__)


def build_router(
    dialogue: DialogueService,
    reminders: ReminderService,
    proactive: ProactiveService | None,
    reflection: ReflectionService | None,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> Router:
    router = Router()

    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        if message.from_user is None:
            return

        await dialogue.register_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )

        await message.answer(
            "Я на связи. Это чистая новая сборка Ии.\n\n"
            "Команды:\n"
            "/health — проверка состояния\n"
            "/settings — настройки сервиса, только владелец\n"
            "/version — версия сборки, только владелец\n"
            "/remember <факт> — закрепить память\n"
            "/reflect — очистить память, только владелец\n"
            "/remind 10m <текст> — напоминание"
        )

    @router.message(Command("health"))
    async def health_handler(message: Message) -> None:
        owner = is_owner(message.from_user.id if message.from_user else None, settings)
        try:
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))
            db_status = "ok"
        except Exception:
            logger.exception("Health DB check failed")
            db_status = "failed"

        if owner:
            await message.answer(
                "app: ok\n"
                f"db: {db_status}\n"
                f"env: {settings.app_env}\n"
                f"version: {settings.app_version}\n"
                f"timezone: {effective_timezone(settings)}\n"
                f"prompt_path: {settings.system_prompt_path}"
            )
            return

        await message.answer("app: ok" if db_status == "ok" else "app: degraded")

    @router.message(Command("settings"))
    async def settings_handler(message: Message) -> None:
        if not is_owner(message.from_user.id if message.from_user else None, settings):
            await message.answer("Эта команда доступна только владельцу.")
            return

        owner_configured = "yes" if settings.owner_telegram_id is not None else "no"
        await message.answer(
            "Текущие настройки без секретов:\n"
            f"APP_ENV={settings.app_env}\n"
            f"APP_VERSION={settings.app_version}\n"
            f"OWNER_TELEGRAM_ID configured={owner_configured}\n"
            f"LOG_LEVEL={settings.log_level}\n"
            f"BOT_TIMEZONE={effective_timezone(settings)}\n"
            f"HISTORY_LIMIT={settings.history_limit}\n"
            f"SYSTEM_PROMPT_PATH={settings.system_prompt_path}\n"
            f"LLM_BASE_URL={settings.llm_base_url}\n"
            f"LLM_MODEL={settings.llm_model}\n"
            f"LLM_TIMEOUT_SECONDS={settings.llm_timeout_seconds}\n"
            f"REMINDER_SCAN_INTERVAL_SECONDS={settings.reminder_scan_interval_seconds}\n"
            f"PROACTIVE_ENABLED={settings.proactive_enabled}\n"
            f"PROACTIVE_SCAN_INTERVAL_SECONDS={settings.proactive_scan_interval_seconds}\n"
            f"PROACTIVE_MIN_DELAY_MINUTES={settings.proactive_min_delay_minutes}\n"
            f"PROACTIVE_MAX_DELAY_MINUTES={settings.proactive_max_delay_minutes}\n"
            f"REFLECTION_ENABLED={settings.reflection_enabled}\n"
            f"REFLECTION_INTERVAL_MINUTES={settings.reflection_interval_minutes}\n"
            f"REFLECTION_KEEP_RECENT_MESSAGES={settings.reflection_keep_recent_messages}\n"
            f"TELEGRAM_IMAGE_MAX_BYTES={settings.telegram_image_max_bytes}"
        )

    @router.message(Command("version"))
    async def version_handler(message: Message) -> None:
        if not is_owner(message.from_user.id if message.from_user else None, settings):
            await message.answer("Эта команда доступна только владельцу.")
            return

        await message.answer(
            "Iya Next Clean\n"
            f"version: {settings.app_version}\n"
            f"env: {settings.app_env}"
        )

    @router.message(Command("remember"))
    async def remember_handler(message: Message) -> None:
        if message.from_user is None:
            return

        payload = _command_payload(message.text or "", "/remember")
        if not payload:
            await message.answer("Формат: /remember <факт для памяти>")
            return

        await dialogue.register_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
        await dialogue.remember(message.from_user.id, payload)
        await message.answer("Запомнила.")

    @router.message(Command("reflect"))
    async def reflect_handler(message: Message) -> None:
        if message.from_user is None:
            return
        if not is_owner(message.from_user.id, settings):
            await message.answer("Эта команда доступна только владельцу.")
            return
        if reflection is None:
            await message.answer("Рефлексия отключена.")
            return

        reflected = await reflection.reflect_user(message.from_user.id)
        await message.answer("Память очищена." if reflected else "Памяти для очистки пока нет.")

    @router.message(Command("remind"))
    async def remind_handler(message: Message) -> None:
        if message.from_user is None:
            return

        payload = _command_payload(message.text or "", "/remind")
        if not payload:
            await message.answer("Формат: /remind 10m текст, /remind 2h текст или /remind 1d текст.")
            return

        await dialogue.register_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )

        try:
            reminder_id = await reminders.create_from_command(
                telegram_user_id=message.from_user.id,
                chat_id=message.chat.id,
                command_payload=payload,
            )
        except ReminderParseError as exc:
            await message.answer(str(exc))
            return

        await message.answer(f"Поставила напоминание. id={reminder_id}")

    @router.message()
    async def dialogue_handler(message: Message) -> None:
        if message.from_user is None:
            return

        text = message.text or message.caption or ""
        image_data_url: str | None = None
        if message.photo:
            try:
                image_data_url = await _download_photo_as_data_url(message, settings)
            except ValueError as exc:
                await message.answer(str(exc))
                return

        if not text and image_data_url is None:
            await message.answer("Пока я обрабатываю только текст и изображения.")
            return

        try:
            await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
            answer = await dialogue.answer(
                telegram_user_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                text=text,
                image_data_url=image_data_url,
            )
            if proactive is not None:
                await proactive.ensure_next_check_in(
                    telegram_user_id=message.from_user.id,
                    chat_id=message.chat.id,
                )
        except Exception:
            logger.exception("Dialogue handler failed")
            await message.answer(
                "Я запустилась, но при обработке сообщения возникла ошибка. "
                "Смотри логи контейнера app."
            )
            return

        await message.answer(answer)

    return router


def _command_payload(text: str, command: str) -> str:
    if not text:
        return ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


async def _download_photo_as_data_url(message: Message, settings: Settings) -> str:
    if not message.photo:
        raise ValueError("В сообщении нет изображения.")

    photo = message.photo[-1]
    if photo.file_size is not None and photo.file_size > settings.telegram_image_max_bytes:
        raise ValueError("Изображение слишком большое для обработки.")

    buffer = BytesIO()
    await message.bot.download(photo, destination=buffer)
    data = buffer.getvalue()
    if len(data) > settings.telegram_image_max_bytes:
        raise ValueError("Изображение слишком большое для обработки.")

    encoded = b64encode(data).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"
