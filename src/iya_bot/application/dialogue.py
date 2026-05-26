from iya_bot.application.prompt_loader import load_system_prompt
from iya_bot.application.ports import LLMClient, MemoryRepository, MessageRepository, UserRepository
from iya_bot.domain.models import ChatMessage


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

        prompt_messages = self._build_prompt_messages(memories=memories, recent=recent)
        response = await self._llm.complete(prompt_messages)

        await self._messages.add_message(telegram_user_id, "assistant", response)
        return response

    def _build_prompt_messages(self, memories: list[str], recent: list[ChatMessage]) -> list[ChatMessage]:
        blocks = [self._system_prompt]

        if memories:
            memory_block = "\n".join(f"- {item}" for item in memories)
            blocks.append(
                "Закреплённая память о пользователе и проекте. "
                "Используй её только когда она действительно релевантна:\n"
                f"{memory_block}"
            )

        messages: list[ChatMessage] = [ChatMessage(role="system", content="\n\n".join(blocks))]
        messages.extend(recent)
        return messages

