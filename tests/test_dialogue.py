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

    async def list_user_ids(self, limit: int = 100) -> list[int]:
        return [int(user["telegram_id"]) for user in self.users[-limit:]]


class FakeMessageRepository:
    def __init__(self) -> None:
        self.messages: list[ChatMessage] = []

    async def add_message(self, telegram_user_id: int, role: str, content: str) -> None:
        self.messages.append(ChatMessage(role=role, content=content))

    async def get_recent_messages(self, telegram_user_id: int, limit: int) -> list[ChatMessage]:
        return self.messages[-limit:]

    async def prune_old_messages(self, telegram_user_id: int, keep_last: int) -> int:
        removed = max(0, len(self.messages) - keep_last)
        self.messages = self.messages[-keep_last:] if keep_last > 0 else []
        return removed


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


<<<<<<< HEAD
async def test_remember_rejects_empty_memory(tmp_path: Path) -> None:
=======
async def test_runtime_context_injected_without_breaking_prompt_order(tmp_path: Path) -> None:
    prompt = tmp_path / "system.md"
    prompt.write_text("Системный промпт", encoding="utf-8")
    messages = FakeMessageRepository()
    memories = FakeMemoryRepository(memories=[], summary=None)
    llm = FakeLLMClient(["Ответ", "Выжимка"])
    dialogue = DialogueService(
        users=FakeUserRepository(),
        messages=messages,
        memories=memories,
        llm=llm,
        history_limit=20,
        system_prompt_path=str(prompt),
        runtime_context_enabled=True,
        timezone_name="Europe/Moscow",
    )

    await dialogue.answer(
        telegram_user_id=7,
        username=None,
        first_name=None,
        last_name=None,
        text="привет",
    )

    call = llm.calls[0]
    # Индекс 0 — по-прежнему основной системный промпт.
    assert call[0].role == "system"
    assert "Системный промпт" in call[0].content
    # Есть второй system-блок с анти-повтором.
    assert any(
        m.role == "system" and "повтор" in str(m.content).lower() for m in call[1:]
    )
    # Последнее сообщение — реплика пользователя.
    assert call[-1] == ChatMessage(role="user", content="привет")


async def test_runtime_context_can_be_disabled(tmp_path: Path) -> None:
    prompt = tmp_path / "system.md"
    prompt.write_text("Системный промпт", encoding="utf-8")
    llm = FakeLLMClient(["Ответ", "Выжимка"])
    dialogue = DialogueService(
        users=FakeUserRepository(),
        messages=FakeMessageRepository(),
        memories=FakeMemoryRepository(memories=[], summary=None),
        llm=llm,
        history_limit=20,
        system_prompt_path=str(prompt),
        runtime_context_enabled=False,
    )

    await dialogue.answer(
        telegram_user_id=7,
        username=None,
        first_name=None,
        last_name=None,
        text="привет",
    )

    call = llm.calls[0]
    system_blocks = [m for m in call if m.role == "system"]
    assert len(system_blocks) == 1
>>>>>>> 1917e25 (Rebuilt full)
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


async def test_answer_can_send_current_image_to_llm(tmp_path: Path) -> None:
    prompt = tmp_path / "system.md"
    prompt.write_text("Системный промпт", encoding="utf-8")
    messages = FakeMessageRepository()
    memories = FakeMemoryRepository(memories=[], summary=None)
    llm = FakeLLMClient(["Ответ по картинке", "Выжимка с картинкой"])
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
        username=None,
        first_name=None,
        last_name=None,
        text="Что на фото?",
        image_data_url="data:image/jpeg;base64,abc",
    )

    assert response == "Ответ по картинке"
    current_user_message = llm.calls[0][-1]
    assert current_user_message.role == "user"
    assert isinstance(current_user_message.content, list)
    assert current_user_message.content[1]["image_url"]["url"] == "data:image/jpeg;base64,abc"
    assert messages.messages[0].content == "Что на фото?\n[Пользователь отправил изображение.]"
