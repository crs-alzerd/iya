import logging

from iya_bot.application.prompt_loader import load_system_prompt
from iya_bot.application.ports import LLMClient, MemoryRepository, MessageRepository, UserRepository
from iya_bot.domain.models import ChatMessage

logger = logging.getLogger(__name__)


class DialogueService:
    def __init__(
        self,
        users: UserRepository,
        messages: MessageRepository,
        memories: MemoryRepository,
        llm: LLMClient,
        history_limit: int,
        system_prompt_path: str | None = None,
    ) -> None:
        self._users = users
        self._messages = messages
        self._memories = memories
        self._llm = llm
        self._history_limit = history_limit
        self._system_prompt = load_system_prompt(system_prompt_path)

    async def register_user(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> None:
        await self._users.upsert_user(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )

    async def remember(self, telegram_user_id: int, content: str) -> None:
        cleaned = content.strip()
        if not cleaned:
            raise ValueError("Нельзя сохранить пустую память.")
        await self._memories.add_memory(telegram_user_id, cleaned)

    async def answer(
        self,
        telegram_user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        text: str,
    ) -> str:
        await self.register_user(
            telegram_id=telegram_user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )

        await self._messages.add_message(telegram_user_id, "user", text)

        recent = await self._messages.get_recent_messages(
            telegram_user_id=telegram_user_id,
            limit=self._history_limit,
        )
        memories = await self._memories.get_memories(telegram_user_id=telegram_user_id)
        summary = await self._memories.get_conversation_summary(
            telegram_user_id=telegram_user_id
        )

        prompt_messages = self._build_prompt_messages(
            memories=memories,
            conversation_summary=summary,
            recent=recent,
        )
        response = await self._llm.complete(prompt_messages)

        await self._messages.add_message(telegram_user_id, "assistant", response)
        await self._update_conversation_summary(
            telegram_user_id=telegram_user_id,
            previous_summary=summary,
            user_text=text,
            assistant_text=response,
        )
        return response

    def _build_prompt_messages(
        self,
        memories: list[str],
        conversation_summary: str | None,
        recent: list[ChatMessage],
    ) -> list[ChatMessage]:
        blocks = [self._system_prompt]

        if memories:
            memory_block = "\n".join(f"- {item}" for item in memories)
            blocks.append(
                "Закреплённая память о пользователе и проекте. "
                "Используй её только когда она действительно релевантна:\n"
                f"{memory_block}"
            )

        if conversation_summary:
            blocks.append(
                "Краткая выжимка предыдущего диалога из базы данных. "
                "Учитывай её как долговременный контекст, но не пересказывай пользователю без нужды:\n"
                f"{conversation_summary}"
            )

        messages: list[ChatMessage] = [
            ChatMessage(role="system", content="\n\n".join(blocks))
        ]
        messages.extend(recent)
        return messages

    async def _update_conversation_summary(
        self,
        telegram_user_id: int,
        previous_summary: str | None,
        user_text: str,
        assistant_text: str,
    ) -> None:
        summary_messages = [
            ChatMessage(
                role="system",
                content=(
                    "Ты обновляешь долговременную память ассистента по диалогу. "
                    "На входе есть прежняя выжимка и новый обмен сообщениями. "
                    "Верни только новую краткую выжимку без вступлений, "
                    "markdown-заголовков и служебных комментариев. "
                    "Сохраняй устойчивые факты о пользователе, проекте, "
                    "предпочтениях, решениях, открытых задачах и важном контексте. "
                    "Удаляй временный шум, повторы и устаревшие детали. Максимум 2500 символов."
                ),
            ),
            ChatMessage(
                role="user",
                content=(
                    "Прежняя выжимка:\n"
                    f"{previous_summary or 'Пока нет.'}\n\n"
                    "Новый обмен:\n"
                    f"Пользователь: {user_text}\n"
                    f"Ассистент: {assistant_text}\n\n"
                    "Обновлённая выжимка:"
                ),
            ),
        ]

        try:
            updated_summary = await self._llm.complete(summary_messages)
            cleaned = updated_summary.strip()
            if cleaned:
                await self._memories.upsert_conversation_summary(telegram_user_id, cleaned)
        except Exception:
            logger.exception(
                "Failed to update conversation summary for telegram_user_id=%s",
                telegram_user_id,
            )
