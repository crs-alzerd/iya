from typing import Sequence

from iya_bot.application.reflection import ReflectionService
from iya_bot.domain.models import ChatMessage


class FakeUserRepository:
    def __init__(self) -> None:
        self.user_ids: list[int] = []

    async def upsert_user(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> None:
        self.user_ids.append(telegram_id)

    async def list_user_ids(self, limit: int = 100) -> list[int]:
        return self.user_ids[-limit:]


class FakeMemoryRepository:
    def __init__(self, memories: list[str], summary: str | None) -> None:
        self.memories = memories
        self.summary = summary

    async def add_memory(self, telegram_user_id: int, content: str) -> None:
        self.memories.append(content)

    async def get_memories(self, telegram_user_id: int, limit: int = 20) -> list[str]:
        return self.memories[-limit:]

    async def get_conversation_summary(self, telegram_user_id: int) -> str | None:
        return self.summary

    async def upsert_conversation_summary(self, telegram_user_id: int, content: str) -> None:
        self.summary = content

    async def replace_memories(self, telegram_user_id: int, memories: list[str]) -> None:
        self.memories = memories


class FakeMessageRepository:
    def __init__(self) -> None:
        self.pruned: list[tuple[int, int]] = []

    async def add_message(self, telegram_user_id: int, role: str, content: str) -> None:
        pass

    async def get_recent_messages(self, telegram_user_id: int, limit: int) -> list[ChatMessage]:
        return []

    async def prune_old_messages(self, telegram_user_id: int, keep_last: int) -> int:
        self.pruned.append((telegram_user_id, keep_last))
        return 0


class FakeLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[list[ChatMessage]] = []

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        self.calls.append(list(messages))
        return self.response


async def test_reflection_replaces_pinned_memory_and_summary() -> None:
    users = FakeUserRepository()
    await users.upsert_user(42, None, None, None)
    memories = FakeMemoryRepository(
        memories=["важный факт", "важный факт", "временный шум"],
        summary="Старая выжимка.",
    )
    messages = FakeMessageRepository()
    llm = FakeLLMClient(
        '{"pinned_memories":["важный факт"],"conversation_summary":"Новая выжимка."}'
    )
    reflection = ReflectionService(
        users=users,
        messages=messages,
        memories=memories,
        llm=llm,
        keep_recent_messages=50,
    )

    reflected = await reflection.reflect_user(42)

    assert reflected is True
    assert memories.memories == ["важный факт"]
    assert memories.summary == "Новая выжимка."
    assert messages.pruned == [(42, 50)]
    assert len(llm.calls) == 1
