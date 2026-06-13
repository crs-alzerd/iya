from __future__ import annotations

from datetime import datetime, time
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, Time, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TelegramUserORM(Base):
    __tablename__ = "telegram_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class MessageORM(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)


class PinnedMemoryORM(Base):
    __tablename__ = "pinned_memories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MemoryFactORM(Base):
    __tablename__ = "memory_facts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(32), default="user", nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    salience_score: Mapped[float] = mapped_column(Float, default=1.0, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True, nullable=False)
    superseded_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Эмбеддинг факта (JSON-список float). NULL — ещё не посчитан, backfill в фоне.
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class MemorySnapshotORM(Base):
    __tablename__ = "memory_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    pinned_memories: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    conversation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ConversationSummaryORM(Base):
    __tablename__ = "conversation_summaries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SelfStateORM(Base):
    __tablename__ = "self_state"

    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"),
        primary_key=True,
    )
    composure: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    warmth_now: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    engagement: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    fatigue: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)
    playfulness: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SelfMemoryORM(Base):
    __tablename__ = "self_memories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    salience_score: Mapped[float] = mapped_column(Float, default=0.5, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class RelationshipStateORM(Base):
    __tablename__ = "relationship_state"

    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"),
        primary_key=True,
    )
    closeness: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)
    trust: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    shared_history_len: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    inside_refs: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class LLMRequestORM(Base):
    __tablename__ = "llm_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    kind: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    tokens_input: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tokens_output: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)


class ModeEventORM(Base):
    __tablename__ = "mode_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    profile: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ReminderORM(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), index=True, default="pending", nullable=False)
    # Planning-система (миграция 0004): различает разовые/повторяющиеся напоминания
    # и подталкивания привычек, плюс связь с привычкой.
    kind: Mapped[str] = mapped_column(String(16), default="one_off", nullable=False)
    recurrence_rule: Mapped[str | None] = mapped_column(String(256), nullable=True)
    habit_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProactiveEventORM(Base):
    __tablename__ = "proactive_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(16), index=True, default="pending", nullable=False)
    planned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    dedup_key: Mapped[str | None] = mapped_column(String(256), unique=True, nullable=True)
    fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# === Planning-система (миграция 0004): планы, привычки, календарь, заметки ===


class PlanningItemORM(Base):
    __tablename__ = "planning_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="todo", index=True, nullable=False)
    priority: Mapped[str] = mapped_column(String(16), default="normal", nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class HabitORM(Base):
    __tablename__ = "habits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    cadence: Mapped[str] = mapped_column(String(16), default="daily", nullable=False)
    schedule_time: Mapped[time | None] = mapped_column(Time(timezone=False), nullable=True)
    target_per_period: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    current_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class HabitCompletionORM(Base):
    __tablename__ = "habit_completions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    habit_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("habits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class CalendarBindingORM(Base):
    __tablename__ = "calendar_bindings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    provider_kind: Mapped[str] = mapped_column(String(16), default="mock", nullable=False)
    calendar_name: Mapped[str] = mapped_column(String(256), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Ссылка на секрет (имя env-переменной / запись в хранилище), не сам пароль.
    credentials_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CalendarEventORM(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    binding_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("calendar_bindings.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    external_id: Mapped[str | None] = mapped_column(String(256), index=True, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="mock", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class NoteLinkORM(Base):
    __tablename__ = "note_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    note_path: Mapped[str] = mapped_column(Text, nullable=False)
    note_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    relation: Mapped[str] = mapped_column(String(16), default="reference", nullable=False)
    planning_item_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    reminder_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    habit_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
