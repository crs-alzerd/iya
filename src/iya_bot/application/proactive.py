import random
from datetime import UTC, datetime, timedelta

from iya_bot.application.ports import (
    LLMClient,
    MemoryRepository,
    MessageRepository,
    ProactiveEventRepository,
)
from iya_bot.application.runtime_context import current_time_in, time_context_line
from iya_bot.domain.enums import LLMRequestKind
from iya_bot.domain.models import ChatMessage

PROACTIVE_KIND_CHECK_IN = "check_in"


class ProactiveService:
    def __init__(
        self,
        events: ProactiveEventRepository,
        messages: MessageRepository,
        memories: MemoryRepository,
        llm: LLMClient,
        history_limit: int,
        min_delay_minutes: int,
        max_delay_minutes: int,
        timezone_name: str = "Europe/Moscow",
        runtime_context_enabled: bool = True,
    ) -> None:
        self._events = events
        self._messages = messages
        self._memories = memories
        self._llm = llm
        self._history_limit = history_limit
        self._min_delay_minutes = min_delay_minutes
        self._max_delay_minutes = max(min_delay_minutes, max_delay_minutes)
        self._timezone_name = timezone_name
        self._runtime_context_enabled = runtime_context_enabled

    async def ensure_next_check_in(self, telegram_user_id: int, chat_id: int) -> None:
        has_pending = await self._events.has_pending_event(
            telegram_user_id=telegram_user_id,
            kind=PROACTIVE_KIND_CHECK_IN,
        )
        if has_pending:
            return

        planned_at = self._next_planned_at()
        dedup_key = f"{telegram_user_id}:{PROACTIVE_KIND_CHECK_IN}:{planned_at.isoformat(timespec='minutes')}"
        await self._events.schedule_event(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            kind=PROACTIVE_KIND_CHECK_IN,
            planned_at=planned_at,
            payload={"reason": "idle_check_in_v1"},
            dedup_key=dedup_key,
        )

    async def generate_check_in(self, telegram_user_id: int) -> str:
        recent = await self._messages.get_recent_messages(
            telegram_user_id=telegram_user_id,
            limit=self._history_limit,
        )
        memories = await self._memories.get_memories(telegram_user_id=telegram_user_id)
        summary = await self._memories.get_conversation_summary(telegram_user_id)

        now = current_time_in(self._timezone_name)
        flavor_directive = _select_flavor(now.hour if now is not None else None, summary=summary)

        context_blocks = []
        if self._runtime_context_enabled and now is not None:
            context_blocks.append(time_context_line(now, self._timezone_name))
        if memories:
            context_blocks.append("Закреплённая память:\n" + "\n".join(f"- {item}" for item in memories))
        if summary:
            context_blocks.append("Выжимка диалога:\n" + summary)

        prompt = [
            ChatMessage(
                role="system",
                content=(
                    "Ты Ия и пишешь пользователю спонтанное сообщение в Telegram. "
                    "Manifest v2: сообщение должно выглядеть мотивированным, будто ты заметила повод, "
                    "а не будто сработал cron. Если по контексту повода нет, напиши очень коротко и ненавязчиво. "
                    "Не упоминай планировщик. Одно сообщение, максимум 500 символов.\n\n"
                    f"Повод и тон для этого сообщения:\n{flavor_directive}"
                ),
            )
        ]
        if context_blocks:
            prompt.append(ChatMessage(role="system", content="\n\n".join(context_blocks)))
        prompt.extend(recent)
        prompt.append(ChatMessage(role="user", content="Сформулируй одно уместное спонтанное сообщение пользователю сейчас."))

        response = await self._llm.complete(prompt, kind=LLMRequestKind.PROACTIVE, telegram_user_id=telegram_user_id)
        return response.strip()

    async def record_sent_check_in(self, telegram_user_id: int, text: str) -> None:
        await self._messages.add_message(telegram_user_id, "assistant", text)

    def _next_planned_at(self) -> datetime:
        delay = random.randint(self._min_delay_minutes, self._max_delay_minutes)
        return datetime.now(UTC) + timedelta(minutes=delay)


_FOLLOW_UP = (
    "Зацепись за конкретную деталь из выжимки или последних сообщений: спроси, как продвинулась "
    "та задача/ситуация, о которой шла речь. Тёпло и по делу, без дежурных «как дела»."
)
_LIGHT_CHECK_IN = (
    "Лёгкий ненавязчивый пинг без явного повода: короткая живая реплика, будто мимолётно вспомнила "
    "о человеке. Не дави, не требуй ответа."
)


def _select_flavor(hour: int | None, *, summary: str | None) -> str:
    """Выбрать повод/тон проактивного сообщения по времени суток и наличию контекста."""
    if hour is not None:
        if 5 <= hour < 11:
            return (
                "Утро. Тёплое короткое доброе утро. Можешь мягко пожелать хорошего дня или спросить "
                "про планы, но без напора и без длинных монологов."
            )
        if hour >= 23 or hour < 5:
            return (
                "Поздняя ночь. Очень тихо и бережно: лёгкое пожелание отдохнуть или короткая забота. "
                "Не вовлекай в долгий разговор, человек может уже засыпать."
            )
        if 17 <= hour < 23:
            return (
                "Вечер. Спокойный тон, можно спросить как прошёл день. " + (_FOLLOW_UP if summary else _LIGHT_CHECK_IN)
            )
    return _FOLLOW_UP if summary else _LIGHT_CHECK_IN
