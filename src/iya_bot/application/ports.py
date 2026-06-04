from abc import ABC, abstractmethod
from datetime import datetime
from typing import Sequence

from iya_bot.domain.models import ChatMessage


class LLMClient(ABC):
    @abstractmethod
    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        raise NotImplementedError


class UserRepository(ABC):
    @abstractmethod
    async def upsert_user(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> None:
        raise NotImplementedError


class MessageRepository(ABC):
    @abstractmethod
    async def add_message(self, telegram_user_id: int, role: str, content: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_recent_messages(self, telegram_user_id: int, limit: int) -> list[ChatMessage]:
        raise NotImplementedError


class MemoryRepository(ABC):
    @abstractmethod
    async def add_memory(self, telegram_user_id: int, content: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_memories(self, telegram_user_id: int, limit: int = 20) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def get_conversation_summary(self, telegram_user_id: int) -> str | None:
        raise NotImplementedError

    @abstractmethod
    async def upsert_conversation_summary(self, telegram_user_id: int, content: str) -> None:
        raise NotImplementedError


class ReminderRepository(ABC):
    @abstractmethod
    async def create_reminder(self, telegram_user_id: int, chat_id: int, text: str, due_at: datetime) -> int:
        raise NotImplementedError
