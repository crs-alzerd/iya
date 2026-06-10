from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
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
