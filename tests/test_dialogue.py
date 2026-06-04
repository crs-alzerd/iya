from pathlib import Path
from typing import Sequence

import pytest

from iya_bot.application.dialogue import DialogueService
from iya_bot.domain.models import ChatMessage


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: list[dict[str, object]] = []

    async def upsert_user(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> None:
        self.users.append(
            {
                "telegram_id": telegram_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
            }
        )


class FakeMessageRepository:
    def __init__(self) -> None:
        self.messages: list[ChatMessage] = []

    async def add_message(self, telegram_user_id: int, role: str, content: str) -> None:
        self.messages.append(ChatMessage(role=role, content=content))

    async def get_recent_messages(self, telegram_user_id: int, limit: int) -> list[ChatMessage]:
        return self.messages[-limit:]


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


class FakeLLMClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[list[ChatMessage]] = []

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        self.calls.append(list(messages))
        return self.responses.pop(0)


async def test_answer_sends_pinned_memory_and_db_summary_to_llm(tmp_path: Path) -> None:
    prompt = tmp_path / "system.md"
    prompt.write_text("Системный промпт", encoding="utf-8")
    messages = FakeMessageRepository()
    memories = FakeMemoryRepository(
        memories=["Пользователь работает над Telegram-ботом Ия."],
        summary="Ранее обсуждали архитектуру: application слой не должен знать про SQLAlchemy.",
    )
    llm = FakeLLMClient(["Ответ пользователю", "Новая краткая выжимка"])
    dialogue = DialogueService(
        users=FakeUserRepository(),
        messages=messages,
        memories=memories,
        llm=llm,
        history_limit=20,
        system_prompt_path=str(prompt),
    )

    response = await dialogue.answer(
        telegram_user_id=42,
        username="user",
        first_name="First",
        last_name=None,
        text="Что сейчас с памятью?",
    )

    assert response == "Ответ пользователю"
    assert len(llm.calls) == 2
    first_api_call = llm.calls[0]
    assert first_api_call[0].role == "system"
    assert "Системный промпт" in first_api_call[0].content
    assert "Пользователь работает над Telegram-ботом Ия." in first_api_call[0].content
    assert "Ранее обсуждали архитектуру" in first_api_call[0].content
    assert first_api_call[-1] == ChatMessage(role="user", content="Что сейчас с памятью?")
    assert messages.messages[-1] == ChatMessage(role="assistant", content="Ответ пользователю")
    assert memories.summary == "Новая краткая выжимка"


async def test_remember_rejects_empty_memory(tmp_path: Path) -> None:
    prompt = tmp_path / "system.md"
    prompt.write_text("Системный промпт", encoding="utf-8")
    dialogue = DialogueService(
        users=FakeUserRepository(),
        messages=FakeMessageRepository(),
        memories=FakeMemoryRepository(memories=[], summary=None),
        llm=FakeLLMClient([]),
        history_limit=20,
        system_prompt_path=str(prompt),
    )

    with pytest.raises(ValueError, match="пустую память"):
        await dialogue.remember(42, "   ")
