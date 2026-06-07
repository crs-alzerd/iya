import random
from datetime import UTC, datetime, timedelta

from iya_bot.application.ports import (
    LLMClient,
    MemoryRepository,
    MessageRepository,
    ProactiveEventRepository,
)
from iya_bot.application.runtime_context import current_time_in, time_context_line
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

        await self._events.schedule_event(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            kind=PROACTIVE_KIND_CHECK_IN,
            planned_at=self._next_planned_at(),
            payload={},
        )

    async def generate_check_in(self, telegram_user_id: int) -> str:
        recent = await self._messages.get_recent_messages(
            telegram_user_id=telegram_user_id,
            limit=self._history_limit,
        )
        memories = await self._memories.get_memories(telegram_user_id=telegram_user_id)
        summary = await self._memories.get_conversation_summary(telegram_user_id)

        context_blocks = []
        if self._runtime_context_enabled:
            now = current_time_in(self._timezone_name)
            if now is not None:
                context_blocks.append(time_context_line(now, self._timezone_name))
        if memories:
            context_blocks.append(
                "Закреплённая память:\n" + "\n".join(f"- {item}" for item in memories)
            )
        if summary:
            context_blocks.append("Выжимка диалога:\n" + summary)

        prompt = [
            ChatMessage(
                role="system",
                content=(
                    "Ты Ия и пишешь пользователю спонтанное сообщение в Telegram. "
                    "Пиши только если это выглядит уместно по контексту. Сообщение "
                    "должно быть коротким, живым и полезным: вопрос, мягкая проверка "
                    "статуса, мысль по проекту или напоминание о незакрытом контексте. "
                    "Не упоминай, что сообщение сгенерировано планировщиком. "
                    "Максимум 500 символов."
                ),
            )
        ]
        if context_blocks:
            prompt.append(ChatMessage(role="system", content="\n\n".join(context_blocks)))
        prompt.extend(recent)
        prompt.append(
            ChatMessage(
                role="user",
                content="Сформулируй одно спонтанное сообщение пользователю сейчас.",
            )
        )

        response = await self._llm.complete(prompt)
        return response.strip()

    async def record_sent_check_in(self, telegram_user_id: int, text: str) -> None:
        await self._messages.add_message(telegram_user_id, "assistant", text)

    def _next_planned_at(self) -> datetime:
        delay = random.randint(self._min_delay_minutes, self._max_delay_minutes)
        return datetime.now(UTC) + timedelta(minutes=delay)
