from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any


ChatContent = str | list[dict[str, Any]]


@dataclass(frozen=True)
class ToolCall:
    """Один вызов инструмента, который запросила модель (OpenAI function calling)."""

    id: str
    name: str
    arguments: str  # сырой JSON-строкой, как его вернул провайдер


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: ChatContent | None = None
    # Для assistant-сообщения, в котором модель попросила вызвать инструменты.
    tool_calls: tuple[ToolCall, ...] | None = None
    # Для сообщения с результатом инструмента (role="tool").
    tool_call_id: str | None = None
    name: str | None = None


@dataclass(frozen=True)
class LLMResponse:
    """Ответ модели в режиме tool-calling: либо текст, либо запросы инструментов."""

    content: str | None
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class DialogueResult:
    """Ответ диалога вместе с подсказкой, сколько сообщений уместно отправить.

    max_messages=1 означает одно цельное сообщение (РП, поддержка, кризис,
    технический разбор). Для лёгкой бытовой переписки допускается больше.
    """

    text: str
    max_messages: int = 1


@dataclass(frozen=True)
class MemoryItem:
    id: int
    text: str
    author: str
    source: str
    confidence: float
    salience_score: float
    status: str
    created_at: datetime | None = None
    last_confirmed_at: datetime | None = None
    superseded_by: int | None = None
    # Эмбеддинг для семантического поиска; None — ещё не посчитан.
    embedding: list[float] | None = None


@dataclass(frozen=True)
class MemorySnapshot:
    id: int
    reason: str
    created_at: datetime | None = None


@dataclass(frozen=True)
class SelfState:
    telegram_user_id: int
    composure: float = 0.8
    warmth_now: float = 0.7
    engagement: float = 0.5
    fatigue: float = 0.2
    playfulness: float = 0.2
    updated_at: datetime | None = None

    def as_prompt_lines(self) -> list[str]:
        return [
            f"composure={self.composure:.2f}",
            f"warmth_now={self.warmth_now:.2f}",
            f"engagement={self.engagement:.2f}",
            f"fatigue={self.fatigue:.2f}",
            f"playfulness={self.playfulness:.2f}",
        ]


@dataclass(frozen=True)
class RelationshipState:
    telegram_user_id: int
    closeness: float = 0.2
    trust: float = 0.3
    shared_history_len: int = 0
    inside_refs: list[int] = field(default_factory=list)
    updated_at: datetime | None = None


@dataclass(frozen=True)
class ModulationVector:
    warmth: float = 0.55
    verbosity: float = 0.55
    technical_precision: float = 0.55
    playfulness: float = 0.2
    intimacy: float = 0.2
    structure: float = 0.55
    temperature_hint: float = 0.75

    def clamp(self) -> "ModulationVector":
        return ModulationVector(
            warmth=_clamp01(self.warmth),
            verbosity=_clamp01(self.verbosity),
            technical_precision=_clamp01(self.technical_precision),
            playfulness=_clamp01(self.playfulness),
            intimacy=_clamp01(self.intimacy),
            structure=_clamp01(self.structure),
            temperature_hint=_clamp01(self.temperature_hint),
        )


@dataclass(frozen=True)
class RoutingDecision:
    profile: str
    vector: ModulationVector
    confidence: float
    reason: str
    crisis: bool = False


@dataclass(frozen=True)
class LLMRequestRecord:
    telegram_user_id: int | None
    kind: str
    provider: str
    model: str
    status: str
    latency_ms: int | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    cost_usd: float | None = None
    error_text: str | None = None


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


# === Planning-система (Obsidian + календарь + планы/привычки) ===
# Доменные сущности planning-подсистемы. Это чистые dataclass'ы без зависимостей
# от инфраструктуры — их читают/возвращают сервисы (`application/planning`),
# а провайдеры и репозитории отображают их в свои представления.


@dataclass(frozen=True)
class PlanningItem:
    """Единица плана: задача или подзадача владельца.

    parent_id связывает подзадачу с родительской задачей (декомпозиция цели).
    scheduled_for — когда задача поставлена в расписание (с учётом занятости
    календаря); due_at — крайний срок.
    """

    id: int
    owner_id: int
    title: str
    description: str | None = None
    status: str = "todo"
    priority: str = "normal"
    due_at: datetime | None = None
    scheduled_for: datetime | None = None
    parent_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class Reminder:
    """Напоминание, которое доставляется владельцу в заданное время.

    kind различает разовое/повторяющееся напоминание и подталкивание привычки
    (habit_nudge). recurrence_rule — текстовое правило повторения (например,
    iCalendar RRULE); habit_id связывает habit_nudge с привычкой.
    """

    id: int
    owner_id: int
    chat_id: int
    text: str
    due_at: datetime
    status: str = "pending"
    kind: str = "one_off"
    recurrence_rule: str | None = None
    habit_id: int | None = None
    created_at: datetime | None = None
    sent_at: datetime | None = None


@dataclass(frozen=True)
class Habit:
    """Привычка с заданной частотой и (опционально) временем напоминания.

    current_streak/last_completed_at — производные от HabitCompletion, хранятся
    денормализованно для быстрых ответов. target_per_period — сколько раз за
    период (день/неделю/месяц) привычку нужно выполнить.
    """

    id: int
    owner_id: int
    title: str
    cadence: str = "daily"
    schedule_time: time | None = None
    target_per_period: int = 1
    reminder_enabled: bool = True
    current_streak: int = 0
    last_completed_at: datetime | None = None
    status: str = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class HabitCompletion:
    """Один факт выполнения привычки. Источник истины для расчёта streak."""

    id: int
    habit_id: int
    completed_at: datetime


@dataclass(frozen=True)
class CalendarEvent:
    """Событие календаря. id присвоен Ией (БД-кэш), external_id — id у провайдера.

    binding_id связывает событие с конкретным подключённым календарём
    (CalendarBinding); source помечает происхождение (mock/caldav/google/ics).
    """

    id: int | None
    owner_id: int
    title: str
    start_at: datetime
    end_at: datetime
    binding_id: int | None = None
    external_id: str | None = None
    all_day: bool = False
    location: str | None = None
    description: str | None = None
    source: str = "mock"


@dataclass(frozen=True)
class CalendarBinding:
    """Подключённый календарь владельца.

    credentials_ref — ссылка на секрет (имя переменной окружения / запись в
    хранилище секретов), а не сам пароль: plaintext-учётки в доменную модель
    не кладём.
    """

    id: int
    owner_id: int
    provider_kind: str
    calendar_name: str
    url: str | None = None
    credentials_ref: str | None = None
    status: str = "active"
    last_synced_at: datetime | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class NoteLink:
    """Связь доменной сущности с заметкой Obsidian-vault по её пути.

    relation описывает роль заметки (source/plan/log/reference). Опциональные
    *_id привязывают заметку к задаче/напоминанию/привычке.
    """

    id: int
    owner_id: int
    note_path: str
    relation: str = "reference"
    note_title: str | None = None
    planning_item_id: int | None = None
    reminder_id: int | None = None
    habit_id: int | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class NoteRef:
    """Результат поиска по vault: путь к заметке, заголовок и фрагмент совпадения."""

    path: str
    title: str | None = None
    snippet: str | None = None


@dataclass(frozen=True)
class WorkflowStep:
    """Один шаг координируемого многошагового действия (результат WorkflowEngine)."""

    title: str
    status: str = "pending"
    detail: str | None = None
    scheduled_for: datetime | None = None
