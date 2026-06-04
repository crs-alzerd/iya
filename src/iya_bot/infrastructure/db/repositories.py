from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from iya_bot.application.ports import MemoryRepository, MessageRepository, ReminderRepository, UserRepository
from iya_bot.domain.models import ChatMessage
from iya_bot.infrastructure.db.models import (
    ConversationSummaryORM,
    MessageORM,
    PinnedMemoryORM,
    ReminderORM,
    TelegramUserORM,
)


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def upsert_user(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> None:
        stmt = insert(TelegramUserORM).values(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[TelegramUserORM.telegram_id],
            set_={
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "updated_at": datetime.now(UTC),
            },
        )

        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()


class SqlAlchemyMessageRepository(MessageRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add_message(self, telegram_user_id: int, role: str, content: str) -> None:
        async with self._session_factory() as session:
            session.add(
                MessageORM(
                    telegram_user_id=telegram_user_id,
                    role=role,
                    content=content,
                )
            )
            await session.commit()

    async def get_recent_messages(self, telegram_user_id: int, limit: int) -> list[ChatMessage]:
        stmt = (
            select(MessageORM)
            .where(MessageORM.telegram_user_id == telegram_user_id)
            .order_by(MessageORM.created_at.desc(), MessageORM.id.desc())
            .limit(limit)
        )

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = list(result.scalars().all())

        rows.reverse()
        return [ChatMessage(role=row.role, content=row.content) for row in rows]


class SqlAlchemyMemoryRepository(MemoryRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add_memory(self, telegram_user_id: int, content: str) -> None:
        async with self._session_factory() as session:
            session.add(
                PinnedMemoryORM(
                    telegram_user_id=telegram_user_id,
                    content=content,
                )
            )
            await session.commit()

    async def get_memories(self, telegram_user_id: int, limit: int = 20) -> list[str]:
        stmt = (
            select(PinnedMemoryORM)
            .where(PinnedMemoryORM.telegram_user_id == telegram_user_id)
            .order_by(PinnedMemoryORM.created_at.desc(), PinnedMemoryORM.id.desc())
            .limit(limit)
        )

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = list(result.scalars().all())

        rows.reverse()
        return [row.content for row in rows]

    async def get_conversation_summary(self, telegram_user_id: int) -> str | None:
        stmt = select(ConversationSummaryORM.content).where(
            ConversationSummaryORM.telegram_user_id == telegram_user_id
        )

        async with self._session_factory() as session:
            result = await session.execute(stmt)

        return result.scalar_one_or_none()

    async def upsert_conversation_summary(self, telegram_user_id: int, content: str) -> None:
        stmt = insert(ConversationSummaryORM).values(
            telegram_user_id=telegram_user_id,
            content=content,
            updated_at=datetime.now(UTC),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[ConversationSummaryORM.telegram_user_id],
            set_={
                "content": content,
                "updated_at": datetime.now(UTC),
            },
        )

        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()


class SqlAlchemyReminderRepository(ReminderRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_reminder(self, telegram_user_id: int, chat_id: int, text: str, due_at: datetime) -> int:
        async with self._session_factory() as session:
            reminder = ReminderORM(
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
                text=text,
                due_at=due_at,
                status="pending",
            )
            session.add(reminder)
            await session.commit()
            await session.refresh(reminder)
            return int(reminder.id)


class ReminderDueRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_due_pending(self, limit: int = 20) -> list[ReminderORM]:
        now = datetime.now(UTC)
        stmt = (
            select(ReminderORM)
            .where(ReminderORM.status == "pending")
            .where(ReminderORM.due_at <= now)
            .order_by(ReminderORM.due_at.asc(), ReminderORM.id.asc())
            .limit(limit)
        )

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            reminders = list(result.scalars().all())

        return reminders

    async def mark_sent(self, reminder_id: int) -> None:
        stmt = (
            update(ReminderORM)
            .where(ReminderORM.id == reminder_id)
            .values(status="sent", sent_at=datetime.now(UTC))
        )

        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def mark_failed(self, reminder_id: int) -> None:
        stmt = (
            update(ReminderORM)
            .where(ReminderORM.id == reminder_id)
            .values(status="failed")
        )

        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()
