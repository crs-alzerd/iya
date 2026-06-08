from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Sequence

from iya_bot.domain.models import (
    ChatMessage,
    LLMRequestRecord,
    LLMResponse,
    MemoryItem,
    MemorySnapshot,
    RelationshipState,
    SearchResult,
    SelfState,
)


class LLMClient(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        kind: str = "dialogue",
        telegram_user_id: int | None = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def complete_tools(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: list[dict],
        kind: str = "dialogue",
        telegram_user_id: int | None = None,
    ) -> LLMResponse:
        """Один шаг tool-calling: модель либо отвечает текстом, либо просит вызвать инструменты."""
        raise NotImplementedError


class WebSearchClient(ABC):
    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        raise NotImplementedError


class PageFetcher(ABC):
    @abstractmethod
    async def fetch(self, url: str) -> str:
        """Скачать страницу и вернуть читабельный текст."""
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

    @abstractmethod
    async def list_user_ids(self, limit: int = 100) -> list[int]:
        raise NotImplementedError


class MessageRepository(ABC):
    @abstractmethod
    async def add_message(self, telegram_user_id: int, role: str, content: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_recent_messages(self, telegram_user_id: int, limit: int) -> list[ChatMessage]:
        raise NotImplementedError

    @abstractmethod
    async def prune_old_messages(self, telegram_user_id: int, keep_last: int) -> int:
        raise NotImplementedError


class MemoryRepository(ABC):
    @abstractmethod
    async def add_memory(self, telegram_user_id: int, content: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def add_extracted_fact(
        self,
        telegram_user_id: int,
        text: str,
        *,
        author: str = "extracted",
        source: str = "extracted",
        confidence: float = 0.7,
        salience: float = 0.6,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_memories(self, telegram_user_id: int, limit: int = 20) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def list_memory_items(self, telegram_user_id: int, include_archived: bool = False, limit: int = 50) -> list[MemoryItem]:
        raise NotImplementedError

    @abstractmethod
    async def archive_memory(self, telegram_user_id: int, memory_id: int) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def get_conversation_summary(self, telegram_user_id: int) -> str | None:
        raise NotImplementedError

    @abstractmethod
    async def upsert_conversation_summary(self, telegram_user_id: int, content: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def replace_memories(self, telegram_user_id: int, memories: list[str]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def create_memory_snapshot(self, telegram_user_id: int, reason: str) -> int:
        raise NotImplementedError

    @abstractmethod
    async def list_memory_snapshots(self, telegram_user_id: int, limit: int = 10) -> list[MemorySnapshot]:
        raise NotImplementedError


class SelfStateRepository(ABC):
    @abstractmethod
    async def get_or_create_state(self, telegram_user_id: int) -> SelfState:
        raise NotImplementedError

    @abstractmethod
    async def upsert_state(self, state: SelfState) -> None:
        raise NotImplementedError


class RelationshipStateRepository(ABC):
    @abstractmethod
    async def get_or_create_relationship(self, telegram_user_id: int) -> RelationshipState:
        raise NotImplementedError

    @abstractmethod
    async def upsert_relationship(self, relationship: RelationshipState) -> None:
        raise NotImplementedError


class LLMRequestRepository(ABC):
    @abstractmethod
    async def add_request_record(self, record: LLMRequestRecord) -> None:
        raise NotImplementedError


class ProactiveEventRepository(ABC):
    @abstractmethod
    async def schedule_event(
        self,
        telegram_user_id: int,
        chat_id: int,
        kind: str,
        planned_at: datetime,
        payload: dict[str, object] | None = None,
        dedup_key: str | None = None,
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    async def has_pending_event(self, telegram_user_id: int, kind: str) -> bool:
        raise NotImplementedError
