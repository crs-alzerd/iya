from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import AsyncIterator, Sequence

from iya_bot.domain.models import (
    CalendarBinding,
    CalendarEvent,
    ChatMessage,
    Habit,
    HabitCompletion,
    LLMRequestRecord,
    LLMResponse,
    MemoryItem,
    MemorySnapshot,
    NoteLink,
    NoteRef,
    PlanningItem,
    RelationshipState,
    Reminder,
    SearchResult,
    SelfState,
    WorkflowStep,
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

    async def complete_stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        kind: str = "dialogue",
        telegram_user_id: int | None = None,
    ) -> AsyncIterator[str]:
        """Потоковый ответ: yield'ит дельты текста. Дефолт — один кусок без стриминга,
        чтобы реализации и фейки без поддержки stream продолжали работать."""
        yield await self.complete(messages, kind=kind, telegram_user_id=telegram_user_id)


class SpeechTranscriber(ABC):
    @abstractmethod
    async def transcribe(self, audio: bytes, *, filename: str = "voice.ogg", language: str | None = None) -> str:
        """Распознать речь в текст. Возвращает пустую строку, если распознать не удалось."""
        raise NotImplementedError


class EmbeddingClient(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Эмбеддинги для списка текстов, в том же порядке."""
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
    async def list_facts_missing_embedding(self, telegram_user_id: int, limit: int = 20) -> list[MemoryItem]:
        raise NotImplementedError

    @abstractmethod
    async def set_fact_embedding(self, telegram_user_id: int, memory_id: int, embedding: list[float]) -> None:
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


# === Planning-система: провайдеры (внешние интеграции за портами) ===
# Реальные реализации (CalDAV/Google/Obsidian-FS/nanogpt/aiogram) подключаются
# позже; на этом этапе используются mock-адаптеры из infrastructure.


class CalendarProvider(ABC):
    """Доступ к календарю владельца. Реальные адаптеры: CalDAV, Google, ICS (RO)."""

    @abstractmethod
    async def list_events(self, owner_id: int, start: datetime, end: datetime) -> list[CalendarEvent]:
        raise NotImplementedError

    @abstractmethod
    async def create_event(self, event: CalendarEvent) -> CalendarEvent:
        """Создать событие. Возвращает событие с проставленным external_id/id."""
        raise NotImplementedError

    @abstractmethod
    async def update_event(self, event: CalendarEvent) -> CalendarEvent:
        raise NotImplementedError

    @abstractmethod
    async def delete_event(self, owner_id: int, external_id: str) -> bool:
        raise NotImplementedError


class NotesProvider(ABC):
    """Доступ к Obsidian-vault. Реальный адаптер: файловая система примонтированного vault."""

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[NoteRef]:
        raise NotImplementedError

    @abstractmethod
    async def read_note(self, path: str) -> str | None:
        """Текст заметки по относительному пути в vault или None, если её нет."""
        raise NotImplementedError

    @abstractmethod
    async def write_note(self, path: str, content: str) -> None:
        """Создать/перезаписать заметку целиком."""
        raise NotImplementedError

    @abstractmethod
    async def append_note(self, path: str, text: str) -> None:
        """Дописать текст в конец заметки (создать, если её нет)."""
        raise NotImplementedError

    @abstractmethod
    async def list_notes(self, folder: str | None = None) -> list[str]:
        """Пути всех заметок (опционально внутри папки)."""
        raise NotImplementedError


class WorkflowEngine(ABC):
    """Координация многошаговых действий: цель -> последовательность шагов."""

    @abstractmethod
    async def plan(self, goal: str, context: str | None = None) -> list[WorkflowStep]:
        raise NotImplementedError

    @abstractmethod
    async def advance(self, steps: list[WorkflowStep], done_title: str) -> list[WorkflowStep]:
        """Отметить шаг выполненным и вернуть обновлённую последовательность."""
        raise NotImplementedError


class NotificationProvider(ABC):
    """Доставка сообщений владельцу. Реальный адаптер обернёт aiogram Bot."""

    @abstractmethod
    async def notify(self, owner_id: int, chat_id: int, text: str) -> None:
        raise NotImplementedError


class ModelProvider(ABC):
    """LLM для planning-подсистемы (отдельно от диалогового LLMClient).

    Реальный адаптер обернёт LLMRouter поверх nanogpt. Метод structured()
    предназначен для запросов, где ожидается машиночитаемый (JSON-подобный)
    ответ — декомпозиция целей, расписание и т.п.
    """

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        raise NotImplementedError

    async def structured(self, prompt: str) -> str:
        """По умолчанию — обычная генерация. Адаптеры могут включить JSON-режим."""
        return await self.generate(prompt)


# === Planning-система: репозитории ===


class PlanningRepository(ABC):
    @abstractmethod
    async def add_item(self, item: PlanningItem) -> PlanningItem:
        raise NotImplementedError

    @abstractmethod
    async def list_items(self, owner_id: int, *, include_done: bool = False, limit: int = 100) -> list[PlanningItem]:
        raise NotImplementedError

    @abstractmethod
    async def update_status(self, owner_id: int, item_id: int, status: str) -> bool:
        raise NotImplementedError


class ReminderRepository(ABC):
    @abstractmethod
    async def add_reminder(self, reminder: Reminder) -> Reminder:
        raise NotImplementedError

    @abstractmethod
    async def list_due(self, now: datetime, limit: int = 50) -> list[Reminder]:
        raise NotImplementedError

    @abstractmethod
    async def list_for_owner(self, owner_id: int, *, include_done: bool = False, limit: int = 100) -> list[Reminder]:
        raise NotImplementedError

    @abstractmethod
    async def mark_sent(self, reminder_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def cancel(self, owner_id: int, reminder_id: int) -> bool:
        raise NotImplementedError


class HabitRepository(ABC):
    @abstractmethod
    async def add_habit(self, habit: Habit) -> Habit:
        raise NotImplementedError

    @abstractmethod
    async def list_habits(self, owner_id: int, *, include_archived: bool = False, limit: int = 100) -> list[Habit]:
        raise NotImplementedError

    @abstractmethod
    async def add_completion(self, completion: HabitCompletion) -> HabitCompletion:
        raise NotImplementedError

    @abstractmethod
    async def list_completions(self, habit_id: int, limit: int = 365) -> list[HabitCompletion]:
        raise NotImplementedError

    @abstractmethod
    async def update_streak(self, habit_id: int, current_streak: int, last_completed_at: datetime) -> None:
        raise NotImplementedError


class CalendarRepository(ABC):
    """БД-кэш событий и хранилище подключённых календарей (CalendarBinding)."""

    @abstractmethod
    async def add_binding(self, binding: CalendarBinding) -> CalendarBinding:
        raise NotImplementedError

    @abstractmethod
    async def list_bindings(self, owner_id: int) -> list[CalendarBinding]:
        raise NotImplementedError

    @abstractmethod
    async def upsert_event(self, event: CalendarEvent) -> CalendarEvent:
        raise NotImplementedError

    @abstractmethod
    async def list_events(self, owner_id: int, start: datetime, end: datetime) -> list[CalendarEvent]:
        raise NotImplementedError


class NoteLinkRepository(ABC):
    @abstractmethod
    async def add_link(self, link: NoteLink) -> NoteLink:
        raise NotImplementedError

    @abstractmethod
    async def list_links(self, owner_id: int, *, planning_item_id: int | None = None) -> list[NoteLink]:
        raise NotImplementedError
