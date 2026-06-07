import json
import logging

from iya_bot.application.ports import LLMClient, MemoryRepository, MessageRepository, UserRepository
from iya_bot.domain.enums import LLMRequestKind
from iya_bot.domain.models import ChatMessage

logger = logging.getLogger(__name__)


class ReflectionService:
    def __init__(
        self,
        users: UserRepository,
        messages: MessageRepository,
        memories: MemoryRepository,
        llm: LLMClient,
        memory_limit: int = 50,
        keep_recent_messages: int = 200,
    ) -> None:
        self._users = users
        self._messages = messages
        self._memories = memories
        self._llm = llm
        self._memory_limit = memory_limit
        self._keep_recent_messages = keep_recent_messages

    async def reflect_user(self, telegram_user_id: int) -> bool:
        pinned = await self._memories.get_memories(telegram_user_id=telegram_user_id, limit=self._memory_limit)
        summary = await self._memories.get_conversation_summary(telegram_user_id)
        if not pinned and not summary:
            return False

        # Manifest v2 safety: snapshot before destructive memory rewrite.
        try:
            await self._memories.create_memory_snapshot(telegram_user_id, reason="reflection_before_rewrite")
        except Exception:
            logger.exception("Failed to create memory snapshot before reflection for telegram_user_id=%s", telegram_user_id)
            return False

        messages = [
            ChatMessage(
                role="system",
                content=(
                    "Ты выполняешь рефлексию памяти ассистента. Нужно удалить шум, дубли, устаревшие детали и временные факты. "
                    "Оставь только то, что пригодится в будущих диалогах: устойчивые сведения о пользователе, проекте, предпочтениях, "
                    "решениях, важных открытых задачах. Manifest v2: не выдумывай новые факты, не стирай спорное без причины. "
                    "Верни только JSON без markdown."
                ),
            ),
            ChatMessage(
                role="user",
                content=(
                    "Текущая закреплённая память:\n"
                    f"{json.dumps(pinned, ensure_ascii=False)}\n\n"
                    "Текущая выжимка диалога:\n"
                    f"{summary or ''}\n\n"
                    "Верни JSON строго такого вида:\n"
                    '{"pinned_memories":["короткий факт"],"conversation_summary":"краткая выжимка до 2500 символов"}'
                ),
            ),
        ]

        try:
            raw = await self._llm.complete(messages, kind=LLMRequestKind.REFLECTION, telegram_user_id=telegram_user_id)
            payload = _parse_json_object(raw)
            new_pinned = _clean_memory_list(payload.get("pinned_memories"))
            new_summary = _clean_summary(payload.get("conversation_summary"))
        except Exception:
            logger.exception("Failed to reflect memory for telegram_user_id=%s", telegram_user_id)
            return False

        await self._memories.replace_memories(telegram_user_id, new_pinned)
        if summary is not None or new_summary:
            await self._memories.upsert_conversation_summary(telegram_user_id, new_summary)
        await self._messages.prune_old_messages(telegram_user_id=telegram_user_id, keep_last=self._keep_recent_messages)
        return True

    async def reflect_recent_users(self, limit: int = 20) -> int:
        reflected = 0
        for telegram_user_id in await self._users.list_user_ids(limit=limit):
            if await self.reflect_user(telegram_user_id):
                reflected += 1
        return reflected


def _parse_json_object(raw: str) -> dict[str, object]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Reflection response is not a JSON object.")
    return data


def _clean_memory_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned[:1000])
    return result[:30]


def _clean_summary(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:2500]
