from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, Text, func
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
