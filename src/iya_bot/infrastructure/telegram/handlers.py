import asyncio
import logging
from base64 import b64encode
from io import BytesIO

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from iya_bot.application.dialogue import DialogueService
from iya_bot.application.humanize import split_into_messages, typing_delay_seconds
from iya_bot.application.memory_control import (
    MemoryControlService,
    format_memory_items,
    format_self_diagnostics,
)
from iya_bot.application.proactive import ProactiveService
from iya_bot.application.reflection import ReflectionService
from iya_bot.config import Settings, effective_timezone, is_owner
from iya_bot.domain.models import DialogueResult

logger = logging.getLogger(__name__)


def build_router(
    dialogue: DialogueService,
    proactive: ProactiveService | None,
    reflection: ReflectionService | None,
    memory_control: MemoryControlService,
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
            "Я на связи. Это сборка Ии под manifest v2.\n\n"
            "Команды:\n"
            "/health — проверка состояния\n"
            "/settings — настройки сервиса, только владелец\n"
            "/version — версия сборки, только владелец\n"
            "/remember <факт> — закрепить память\n"
            "/memory — показать активную память\n"
            "/summary — показать выжимку диалога\n"
            "/forget <id> — архивировать факт памяти\n"
            "/memory_backup — snapshot памяти\n"
            "/whoami_to_you — self/relationship диагностика\n"
            "/reflect — очистить память, только владелец"
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
                f"prompt_path: {settings.system_prompt_path}\n"
                f"manifest_v2: prompt_builder={settings.prompt_builder_v2_enabled}, "
                f"mode_router={settings.mode_router_enabled}, self_state={settings.self_state_enabled}"
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
            f"PROACTIVE_ENABLED={settings.proactive_enabled}\n"
            f"REFLECTION_ENABLED={settings.reflection_enabled}\n"
            f"TELEGRAM_IMAGE_MAX_BYTES={settings.telegram_image_max_bytes}\n"
            f"VISION_ENABLED={settings.vision_enabled}\n"
            "Manifest v2 flags:\n"
            f"MEMORY_FACTS_ENABLED={settings.memory_facts_enabled}\n"
            f"SELF_STATE_ENABLED={settings.self_state_enabled}\n"
            f"RELATIONSHIP_STATE_ENABLED={settings.relationship_state_enabled}\n"
            f"MODE_ROUTER_ENABLED={settings.mode_router_enabled}\n"
            f"PROMPT_BUILDER_V2_ENABLED={settings.prompt_builder_v2_enabled}\n"
            f"PROMPT_TOKEN_BUDGET={settings.prompt_token_budget}\n"
            f"LLM_LOGGING_ENABLED={settings.llm_logging_enabled}\n"
            "Tools / memory:\n"
            f"TOOLS_ENABLED={settings.tools_enabled}\n"
            f"WEB_SEARCH_ENABLED={settings.web_search_enabled}\n"
            f"FETCH_URL_ENABLED={settings.fetch_url_enabled}\n"
            f"REMEMBER_TOOL_ENABLED={settings.remember_tool_enabled}\n"
            f"AUTO_MEMORY_ENABLED={settings.auto_memory_enabled}"
        )

    @router.message(Command("version"))
    async def version_handler(message: Message) -> None:
        if not is_owner(message.from_user.id if message.from_user else None, settings):
            await message.answer("Эта команда доступна только владельцу.")
            return
        await message.answer(f"Iya\nversion: {settings.app_version}\nenv: {settings.app_env}\nmanifest: v2 core refactor")

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

    @router.message(Command("memory"))
    async def memory_handler(message: Message) -> None:
        if message.from_user is None:
            return
        if not is_owner(message.from_user.id, settings):
            await message.answer("Эта команда доступна только владельцу.")
            return
        items = await memory_control.list_memory(message.from_user.id)
        await message.answer(format_memory_items(items))

    @router.message(Command("summary"))
    async def summary_handler(message: Message) -> None:
        if message.from_user is None:
            return
        if not is_owner(message.from_user.id, settings):
            await message.answer("Эта команда доступна только владельцу.")
            return
        summary = await memory_control.get_summary(message.from_user.id)
        await message.answer(summary or "Выжимки диалога пока нет.")

    @router.message(Command("forget"))
    async def forget_handler(message: Message) -> None:
        if message.from_user is None:
            return
        if not is_owner(message.from_user.id, settings):
            await message.answer("Эта команда доступна только владельцу.")
            return
        payload = _command_payload(message.text or "", "/forget")
        try:
            memory_id = int(payload)
        except ValueError:
            await message.answer("Формат: /forget <id>")
            return
        ok = await memory_control.forget(message.from_user.id, memory_id)
        await message.answer("Факт архивирован." if ok else "Факт с таким id не найден.")

    @router.message(Command("memory_backup"))
    async def memory_backup_handler(message: Message) -> None:
        if message.from_user is None:
            return
        if not is_owner(message.from_user.id, settings):
            await message.answer("Эта команда доступна только владельцу.")
            return
        snapshot_id = await memory_control.create_snapshot(message.from_user.id, reason="manual_owner_backup")
        await message.answer(f"Snapshot памяти создан. id={snapshot_id}")

    @router.message(Command("whoami_to_you"))
    async def whoami_handler(message: Message) -> None:
        if message.from_user is None:
            return
        if not is_owner(message.from_user.id, settings):
            await message.answer("Эта команда доступна только владельцу.")
            return
        state = await memory_control.get_self_state(message.from_user.id)
        relationship = await memory_control.get_relationship(message.from_user.id)
        await message.answer(format_self_diagnostics(state, relationship))

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
        await message.answer("Память очищена. Snapshot создан перед изменением." if reflected else "Памяти для очистки пока нет или snapshot не создан.")

    @router.message()
    async def dialogue_handler(message: Message) -> None:
        if message.from_user is None:
            return
        text = message.text or message.caption or ""
        image_data_url: str | None = None
        if message.photo:
            if not settings.vision_enabled:
                await message.answer("Сейчас vision-контур отключён. Я могу ответить на подпись, но не прочитаю само изображение.")
                return
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
                await proactive.ensure_next_check_in(telegram_user_id=message.from_user.id, chat_id=message.chat.id)
        except Exception:
            logger.exception("Dialogue handler failed")
            await message.answer("Я запустилась, но при обработке сообщения возникла ошибка. Смотри логи контейнера app.")
            return
        await _send_humanized(message, answer, settings)

    return router


async def _send_humanized(message: Message, answer: DialogueResult, settings: Settings) -> None:
    if not settings.humanize_enabled:
        max_chunks = 1
    else:
        # Профиль диалога диктует верхнюю границу (1 — цельный ответ, 2 — болтовня).
        # Глобальный humanize_max_chunks остаётся жёстким потолком сверху.
        max_chunks = min(settings.humanize_max_chunks, answer.max_messages)
    chunks = split_into_messages(answer.text, max_chunks=max(1, max_chunks))
    if not chunks:
        return
    for index, chunk in enumerate(chunks):
        if settings.humanize_enabled and index > 0:
            try:
                await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
            except Exception:
                logger.debug("send_chat_action failed", exc_info=True)
            delay = typing_delay_seconds(
                chunk,
                ms_per_char=settings.humanize_ms_per_char,
                min_seconds=settings.humanize_min_delay_seconds,
                max_seconds=settings.humanize_max_delay_seconds,
            )
            await asyncio.sleep(delay)
        await message.answer(chunk)


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
