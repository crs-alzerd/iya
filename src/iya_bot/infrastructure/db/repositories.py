from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from iya_bot.application.ports import (
    LLMRequestRepository,
    MemoryRepository,
    MessageRepository,
    ProactiveEventRepository,
    RelationshipStateRepository,
    ReminderRepository,
    SelfStateRepository,
    UserRepository,
)
from iya_bot.domain.models import (
    ChatMessage,
    LLMRequestRecord,
    MemoryItem,
    MemorySnapshot,
    RelationshipState,
    SelfState,
)
from iya_bot.infrastructure.db.models import (
    ConversationSummaryORM,
    LLMRequestORM,
    MemoryFactORM,
    MemorySnapshotORM,
    MessageORM,
    PinnedMemoryORM,
    ProactiveEventORM,
    RelationshipStateORM,
    ReminderORM,
    SelfStateORM,
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

    async def list_user_ids(self, limit: int = 100) -> list[int]:
        stmt = (
            select(TelegramUserORM.telegram_id)
            .order_by(TelegramUserORM.updated_at.desc(), TelegramUserORM.id.desc())
            .limit(limit)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
        return [int(row) for row in result.scalars().all()]


class SqlAlchemyMessageRepository(MessageRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add_message(self, telegram_user_id: int, role: str, content: str) -> None:
        async with self._session_factory() as session:
            session.add(MessageORM(telegram_user_id=telegram_user_id, role=role, content=content))
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

    async def prune_old_messages(self, telegram_user_id: int, keep_last: int) -> int:
        if keep_last <= 0:
            stmt = delete(MessageORM).where(MessageORM.telegram_user_id == telegram_user_id)
        else:
            keep_ids = (
                select(MessageORM.id)
                .where(MessageORM.telegram_user_id == telegram_user_id)
                .order_by(MessageORM.created_at.desc(), MessageORM.id.desc())
                .limit(keep_last)
            )
            stmt = (
                delete(MessageORM)
                .where(MessageORM.telegram_user_id == telegram_user_id)
                .where(MessageORM.id.not_in(keep_ids))
            )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            await session.commit()
        return int(result.rowcount or 0)


class SqlAlchemyMemoryRepository(MemoryRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add_memory(self, telegram_user_id: int, content: str) -> None:
        cleaned = content.strip()
        async with self._session_factory() as session:
            session.add(PinnedMemoryORM(telegram_user_id=telegram_user_id, content=cleaned))
            session.add(
                MemoryFactORM(
                    telegram_user_id=telegram_user_id,
                    text=cleaned,
                    author="user",
                    source="manual",
                    confidence=1.0,
                    salience_score=1.0,
                    status="active",
                    last_confirmed_at=datetime.now(UTC),
                )
            )
            await session.commit()

    async def get_memories(self, telegram_user_id: int, limit: int = 20) -> list[str]:
        facts = await self.list_memory_items(telegram_user_id, include_archived=False, limit=limit)
        if facts:
            return [fact.text for fact in facts if fact.status == "active"]

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

    async def list_memory_items(self, telegram_user_id: int, include_archived: bool = False, limit: int = 50) -> list[MemoryItem]:
        stmt = select(MemoryFactORM).where(MemoryFactORM.telegram_user_id == telegram_user_id)
        if not include_archived:
            stmt = stmt.where(MemoryFactORM.status == "active")
        stmt = stmt.order_by(MemoryFactORM.salience_score.desc(), MemoryFactORM.created_at.desc()).limit(limit)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = list(result.scalars().all())
        return [
            MemoryItem(
                id=int(row.id),
                text=row.text,
                author=row.author,
                source=row.source,
                confidence=float(row.confidence),
                salience_score=float(row.salience_score),
                status=row.status,
                created_at=row.created_at,
                last_confirmed_at=row.last_confirmed_at,
                superseded_by=row.superseded_by,
            )
            for row in rows
        ]

    async def archive_memory(self, telegram_user_id: int, memory_id: int) -> bool:
        stmt = (
            update(MemoryFactORM)
            .where(MemoryFactORM.telegram_user_id == telegram_user_id)
            .where(MemoryFactORM.id == memory_id)
            .values(status="archived", updated_at=datetime.now(UTC))
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            await session.commit()
        return bool(result.rowcount)

    async def get_conversation_summary(self, telegram_user_id: int) -> str | None:
        stmt = select(ConversationSummaryORM.content).where(ConversationSummaryORM.telegram_user_id == telegram_user_id)
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
            set_={"content": content, "updated_at": datetime.now(UTC)},
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def replace_memories(self, telegram_user_id: int, memories: list[str]) -> None:
        async with self._session_factory() as session:
            await session.execute(delete(PinnedMemoryORM).where(PinnedMemoryORM.telegram_user_id == telegram_user_id))
            await session.execute(
                update(MemoryFactORM)
                .where(MemoryFactORM.telegram_user_id == telegram_user_id)
                .where(MemoryFactORM.status == "active")
                .values(status="archived", updated_at=datetime.now(UTC))
            )
            for memory in memories:
                cleaned = memory.strip()
                if not cleaned:
                    continue
                session.add(PinnedMemoryORM(telegram_user_id=telegram_user_id, content=cleaned))
                session.add(
                    MemoryFactORM(
                        telegram_user_id=telegram_user_id,
                        text=cleaned,
                        author="extracted",
                        source="reflection",
                        confidence=0.9,
                        salience_score=0.8,
                        status="active",
                        last_confirmed_at=datetime.now(UTC),
                    )
                )
            await session.commit()

    async def create_memory_snapshot(self, telegram_user_id: int, reason: str) -> int:
        memories = await self.get_memories(telegram_user_id, limit=100)
        summary = await self.get_conversation_summary(telegram_user_id)
        async with self._session_factory() as session:
            snapshot = MemorySnapshotORM(
                telegram_user_id=telegram_user_id,
                pinned_memories=memories,
                conversation_summary=summary,
                reason=reason[:128],
            )
            session.add(snapshot)
            await session.commit()
            await session.refresh(snapshot)
            return int(snapshot.id)

    async def list_memory_snapshots(self, telegram_user_id: int, limit: int = 10) -> list[MemorySnapshot]:
        stmt = (
            select(MemorySnapshotORM)
            .where(MemorySnapshotORM.telegram_user_id == telegram_user_id)
            .order_by(MemorySnapshotORM.created_at.desc(), MemorySnapshotORM.id.desc())
            .limit(limit)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = list(result.scalars().all())
        return [MemorySnapshot(id=int(row.id), reason=row.reason, created_at=row.created_at) for row in rows]


class SqlAlchemySelfStateRepository(SelfStateRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_or_create_state(self, telegram_user_id: int) -> SelfState:
        stmt = select(SelfStateORM).where(SelfStateORM.telegram_user_id == telegram_user_id)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                row = SelfStateORM(telegram_user_id=telegram_user_id)
                session.add(row)
                await session.commit()
                await session.refresh(row)
        return SelfState(
            telegram_user_id=telegram_user_id,
            composure=float(row.composure),
            warmth_now=float(row.warmth_now),
            engagement=float(row.engagement),
            fatigue=float(row.fatigue),
            playfulness=float(row.playfulness),
            updated_at=row.updated_at,
        )

    async def upsert_state(self, state: SelfState) -> None:
        stmt = insert(SelfStateORM).values(
            telegram_user_id=state.telegram_user_id,
            composure=state.composure,
            warmth_now=state.warmth_now,
            engagement=state.engagement,
            fatigue=state.fatigue,
            playfulness=state.playfulness,
            updated_at=datetime.now(UTC),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[SelfStateORM.telegram_user_id],
            set_={
                "composure": state.composure,
                "warmth_now": state.warmth_now,
                "engagement": state.engagement,
                "fatigue": state.fatigue,
                "playfulness": state.playfulness,
                "updated_at": datetime.now(UTC),
            },
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()


class SqlAlchemyRelationshipStateRepository(RelationshipStateRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_or_create_relationship(self, telegram_user_id: int) -> RelationshipState:
        stmt = select(RelationshipStateORM).where(RelationshipStateORM.telegram_user_id == telegram_user_id)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                row = RelationshipStateORM(telegram_user_id=telegram_user_id)
                session.add(row)
                await session.commit()
                await session.refresh(row)
        return RelationshipState(
            telegram_user_id=telegram_user_id,
            closeness=float(row.closeness),
            trust=float(row.trust),
            shared_history_len=int(row.shared_history_len),
            inside_refs=list(row.inside_refs or []),
            updated_at=row.updated_at,
        )

    async def upsert_relationship(self, relationship: RelationshipState) -> None:
        stmt = insert(RelationshipStateORM).values(
            telegram_user_id=relationship.telegram_user_id,
            closeness=relationship.closeness,
            trust=relationship.trust,
            shared_history_len=relationship.shared_history_len,
            inside_refs=relationship.inside_refs,
            updated_at=datetime.now(UTC),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[RelationshipStateORM.telegram_user_id],
            set_={
                "closeness": relationship.closeness,
                "trust": relationship.trust,
                "shared_history_len": relationship.shared_history_len,
                "inside_refs": relationship.inside_refs,
                "updated_at": datetime.now(UTC),
            },
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()


class SqlAlchemyLLMRequestRepository(LLMRequestRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add_request_record(self, record: LLMRequestRecord) -> None:
        async with self._session_factory() as session:
            session.add(
                LLMRequestORM(
                    telegram_user_id=record.telegram_user_id,
                    kind=record.kind,
                    provider=record.provider,
                    model=record.model,
                    status=record.status,
                    tokens_input=record.tokens_input,
                    tokens_output=record.tokens_output,
                    cost_usd=record.cost_usd,
                    latency_ms=record.latency_ms,
                    error_text=record.error_text,
                )
            )
            await session.commit()


class SqlAlchemyReminderRepository(ReminderRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_reminder(self, telegram_user_id: int, chat_id: int, text: str, due_at: datetime) -> int:
        async with self._session_factory() as session:
            reminder = ReminderORM(telegram_user_id=telegram_user_id, chat_id=chat_id, text=text, due_at=due_at, status="pending")
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
            return list(result.scalars().all())

    async def mark_sent(self, reminder_id: int) -> None:
        stmt = update(ReminderORM).where(ReminderORM.id == reminder_id).values(status="sent", sent_at=datetime.now(UTC))
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def mark_failed(self, reminder_id: int) -> None:
        stmt = update(ReminderORM).where(ReminderORM.id == reminder_id).values(status="failed")
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()


class SqlAlchemyProactiveEventRepository(ProactiveEventRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def schedule_event(
        self,
        telegram_user_id: int,
        chat_id: int,
        kind: str,
        planned_at: datetime,
        payload: dict[str, object] | None = None,
        dedup_key: str | None = None,
    ) -> int:
        async with self._session_factory() as session:
            event = ProactiveEventORM(
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
                kind=kind,
                payload=payload or {},
                status="pending",
                planned_at=planned_at,
                dedup_key=dedup_key,
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)
            return int(event.id)

    async def has_pending_event(self, telegram_user_id: int, kind: str) -> bool:
        stmt = (
            select(ProactiveEventORM.id)
            .where(ProactiveEventORM.telegram_user_id == telegram_user_id)
            .where(ProactiveEventORM.kind == kind)
            .where(ProactiveEventORM.status == "pending")
            .limit(1)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None


class ProactiveEventDueRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_due_pending(self, limit: int = 10) -> list[ProactiveEventORM]:
        now = datetime.now(UTC)
        stmt = (
            select(ProactiveEventORM)
            .where(ProactiveEventORM.status == "pending")
            .where(ProactiveEventORM.planned_at <= now)
            .order_by(ProactiveEventORM.planned_at.asc(), ProactiveEventORM.id.asc())
            .limit(limit)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def mark_fired(self, event_id: int) -> bool:
        stmt = (
            update(ProactiveEventORM)
            .where(ProactiveEventORM.id == event_id)
            .where(ProactiveEventORM.fired_at.is_(None))
            .values(fired_at=datetime.now(UTC))
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            await session.commit()
        return bool(result.rowcount)

    async def mark_sent(self, event_id: int) -> None:
        stmt = update(ProactiveEventORM).where(ProactiveEventORM.id == event_id).values(status="sent", sent_at=datetime.now(UTC))
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def mark_failed(self, event_id: int) -> None:
        stmt = update(ProactiveEventORM).where(ProactiveEventORM.id == event_id).values(status="failed")
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()
