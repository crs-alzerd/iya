from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from iya_bot.application.ports import (
    CalendarRepository,
    HabitRepository,
    LLMRequestRepository,
    MemoryRepository,
    MessageRepository,
    NoteLinkRepository,
    PlanningRepository,
    ProactiveEventRepository,
    RelationshipStateRepository,
    ReminderRepository,
    SelfStateRepository,
    UserRepository,
)
from iya_bot.domain.models import (
    CalendarBinding,
    CalendarEvent,
    ChatMessage,
    Habit,
    HabitCompletion,
    LLMRequestRecord,
    MemoryItem,
    MemorySnapshot,
    NoteLink,
    PlanningItem,
    RelationshipState,
    Reminder,
    SelfState,
)
from iya_bot.infrastructure.db.models import (
    CalendarBindingORM,
    CalendarEventORM,
    ConversationSummaryORM,
    HabitCompletionORM,
    HabitORM,
    LLMRequestORM,
    MemoryFactORM,
    MemorySnapshotORM,
    MessageORM,
    NoteLinkORM,
    PinnedMemoryORM,
    PlanningItemORM,
    ProactiveEventORM,
    RelationshipStateORM,
    ReminderORM,
    SelfStateORM,
    TelegramUserORM,
)


def _to_memory_item(row: MemoryFactORM) -> MemoryItem:
    return MemoryItem(
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
        embedding=list(row.embedding) if row.embedding else None,
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
        cleaned = text.strip()
        if not cleaned:
            return
        async with self._session_factory() as session:
            session.add(
                MemoryFactORM(
                    telegram_user_id=telegram_user_id,
                    text=cleaned,
                    author=author,
                    source=source,
                    confidence=confidence,
                    salience_score=salience,
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
        return [_to_memory_item(row) for row in rows]

    async def list_facts_missing_embedding(self, telegram_user_id: int, limit: int = 20) -> list[MemoryItem]:
        stmt = (
            select(MemoryFactORM)
            .where(MemoryFactORM.telegram_user_id == telegram_user_id)
            .where(MemoryFactORM.status == "active")
            .where(MemoryFactORM.embedding.is_(None))
            .order_by(MemoryFactORM.created_at.desc(), MemoryFactORM.id.desc())
            .limit(limit)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = list(result.scalars().all())
        return [_to_memory_item(row) for row in rows]

    async def set_fact_embedding(self, telegram_user_id: int, memory_id: int, embedding: list[float]) -> None:
        stmt = (
            update(MemoryFactORM)
            .where(MemoryFactORM.telegram_user_id == telegram_user_id)
            .where(MemoryFactORM.id == memory_id)
            .values(embedding=embedding, updated_at=datetime.now(UTC))
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

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


# === Planning-система: репозитории ===


def _to_planning_item(row: PlanningItemORM) -> PlanningItem:
    return PlanningItem(
        id=int(row.id),
        owner_id=int(row.owner_id),
        title=row.title,
        description=row.description,
        status=row.status,
        priority=row.priority,
        due_at=row.due_at,
        scheduled_for=row.scheduled_for,
        parent_id=int(row.parent_id) if row.parent_id is not None else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_reminder(row: ReminderORM) -> Reminder:
    return Reminder(
        id=int(row.id),
        owner_id=int(row.telegram_user_id),
        chat_id=int(row.chat_id),
        text=row.text,
        due_at=row.due_at,
        status=row.status,
        kind=row.kind,
        recurrence_rule=row.recurrence_rule,
        habit_id=int(row.habit_id) if row.habit_id is not None else None,
        created_at=row.created_at,
        sent_at=row.sent_at,
    )


def _to_habit(row: HabitORM) -> Habit:
    return Habit(
        id=int(row.id),
        owner_id=int(row.owner_id),
        title=row.title,
        cadence=row.cadence,
        schedule_time=row.schedule_time,
        target_per_period=int(row.target_per_period),
        reminder_enabled=bool(row.reminder_enabled),
        current_streak=int(row.current_streak),
        last_completed_at=row.last_completed_at,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_calendar_event(row: CalendarEventORM) -> CalendarEvent:
    return CalendarEvent(
        id=int(row.id),
        owner_id=int(row.owner_id),
        title=row.title,
        start_at=row.start_at,
        end_at=row.end_at,
        binding_id=int(row.binding_id) if row.binding_id is not None else None,
        external_id=row.external_id,
        all_day=bool(row.all_day),
        location=row.location,
        description=row.description,
        source=row.source,
    )


def _to_calendar_binding(row: CalendarBindingORM) -> CalendarBinding:
    return CalendarBinding(
        id=int(row.id),
        owner_id=int(row.owner_id),
        provider_kind=row.provider_kind,
        calendar_name=row.calendar_name,
        url=row.url,
        credentials_ref=row.credentials_ref,
        status=row.status,
        last_synced_at=row.last_synced_at,
        created_at=row.created_at,
    )


def _to_note_link(row: NoteLinkORM) -> NoteLink:
    return NoteLink(
        id=int(row.id),
        owner_id=int(row.owner_id),
        note_path=row.note_path,
        relation=row.relation,
        note_title=row.note_title,
        planning_item_id=int(row.planning_item_id) if row.planning_item_id is not None else None,
        reminder_id=int(row.reminder_id) if row.reminder_id is not None else None,
        habit_id=int(row.habit_id) if row.habit_id is not None else None,
        created_at=row.created_at,
    )


class SqlAlchemyPlanningRepository(PlanningRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add_item(self, item: PlanningItem) -> PlanningItem:
        async with self._session_factory() as session:
            row = PlanningItemORM(
                owner_id=item.owner_id,
                title=item.title,
                description=item.description,
                status=item.status,
                priority=item.priority,
                due_at=item.due_at,
                scheduled_for=item.scheduled_for,
                parent_id=item.parent_id,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _to_planning_item(row)

    async def list_items(self, owner_id: int, *, include_done: bool = False, limit: int = 100) -> list[PlanningItem]:
        stmt = select(PlanningItemORM).where(PlanningItemORM.owner_id == owner_id)
        if not include_done:
            stmt = stmt.where(PlanningItemORM.status.not_in(["done", "cancelled"]))
        stmt = stmt.order_by(PlanningItemORM.scheduled_for.asc().nullslast(), PlanningItemORM.id.asc()).limit(limit)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = list(result.scalars().all())
        return [_to_planning_item(row) for row in rows]

    async def update_status(self, owner_id: int, item_id: int, status: str) -> bool:
        stmt = (
            update(PlanningItemORM)
            .where(PlanningItemORM.owner_id == owner_id)
            .where(PlanningItemORM.id == item_id)
            .values(status=status, updated_at=datetime.now(UTC))
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            await session.commit()
        return bool(result.rowcount)


class SqlAlchemyReminderRepository(ReminderRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add_reminder(self, reminder: Reminder) -> Reminder:
        async with self._session_factory() as session:
            row = ReminderORM(
                telegram_user_id=reminder.owner_id,
                chat_id=reminder.chat_id,
                text=reminder.text,
                due_at=reminder.due_at,
                status=reminder.status,
                kind=reminder.kind,
                recurrence_rule=reminder.recurrence_rule,
                habit_id=reminder.habit_id,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _to_reminder(row)

    async def list_due(self, now: datetime, limit: int = 50) -> list[Reminder]:
        stmt = (
            select(ReminderORM)
            .where(ReminderORM.status == "pending")
            .where(ReminderORM.due_at <= now)
            .order_by(ReminderORM.due_at.asc(), ReminderORM.id.asc())
            .limit(limit)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = list(result.scalars().all())
        return [_to_reminder(row) for row in rows]

    async def list_for_owner(self, owner_id: int, *, include_done: bool = False, limit: int = 100) -> list[Reminder]:
        stmt = select(ReminderORM).where(ReminderORM.telegram_user_id == owner_id)
        if not include_done:
            stmt = stmt.where(ReminderORM.status == "pending")
        stmt = stmt.order_by(ReminderORM.due_at.asc(), ReminderORM.id.asc()).limit(limit)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = list(result.scalars().all())
        return [_to_reminder(row) for row in rows]

    async def mark_sent(self, reminder_id: int) -> None:
        stmt = (
            update(ReminderORM)
            .where(ReminderORM.id == reminder_id)
            .values(status="sent", sent_at=datetime.now(UTC))
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def cancel(self, owner_id: int, reminder_id: int) -> bool:
        stmt = (
            update(ReminderORM)
            .where(ReminderORM.telegram_user_id == owner_id)
            .where(ReminderORM.id == reminder_id)
            .where(ReminderORM.status == "pending")
            .values(status="cancelled")
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            await session.commit()
        return bool(result.rowcount)


class SqlAlchemyHabitRepository(HabitRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add_habit(self, habit: Habit) -> Habit:
        async with self._session_factory() as session:
            row = HabitORM(
                owner_id=habit.owner_id,
                title=habit.title,
                cadence=habit.cadence,
                schedule_time=habit.schedule_time,
                target_per_period=habit.target_per_period,
                reminder_enabled=habit.reminder_enabled,
                current_streak=habit.current_streak,
                last_completed_at=habit.last_completed_at,
                status=habit.status,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _to_habit(row)

    async def list_habits(self, owner_id: int, *, include_archived: bool = False, limit: int = 100) -> list[Habit]:
        stmt = select(HabitORM).where(HabitORM.owner_id == owner_id)
        if not include_archived:
            stmt = stmt.where(HabitORM.status != "archived")
        stmt = stmt.order_by(HabitORM.id.asc()).limit(limit)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = list(result.scalars().all())
        return [_to_habit(row) for row in rows]

    async def add_completion(self, completion: HabitCompletion) -> HabitCompletion:
        async with self._session_factory() as session:
            row = HabitCompletionORM(habit_id=completion.habit_id, completed_at=completion.completed_at)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return HabitCompletion(id=int(row.id), habit_id=int(row.habit_id), completed_at=row.completed_at)

    async def list_completions(self, habit_id: int, limit: int = 365) -> list[HabitCompletion]:
        stmt = (
            select(HabitCompletionORM)
            .where(HabitCompletionORM.habit_id == habit_id)
            .order_by(HabitCompletionORM.completed_at.desc(), HabitCompletionORM.id.desc())
            .limit(limit)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = list(result.scalars().all())
        return [HabitCompletion(id=int(row.id), habit_id=int(row.habit_id), completed_at=row.completed_at) for row in rows]

    async def update_streak(self, habit_id: int, current_streak: int, last_completed_at: datetime) -> None:
        stmt = (
            update(HabitORM)
            .where(HabitORM.id == habit_id)
            .values(current_streak=current_streak, last_completed_at=last_completed_at, updated_at=datetime.now(UTC))
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()


class SqlAlchemyCalendarRepository(CalendarRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add_binding(self, binding: CalendarBinding) -> CalendarBinding:
        async with self._session_factory() as session:
            row = CalendarBindingORM(
                owner_id=binding.owner_id,
                provider_kind=binding.provider_kind,
                calendar_name=binding.calendar_name,
                url=binding.url,
                credentials_ref=binding.credentials_ref,
                status=binding.status,
                last_synced_at=binding.last_synced_at,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _to_calendar_binding(row)

    async def list_bindings(self, owner_id: int) -> list[CalendarBinding]:
        stmt = select(CalendarBindingORM).where(CalendarBindingORM.owner_id == owner_id).order_by(CalendarBindingORM.id.asc())
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = list(result.scalars().all())
        return [_to_calendar_binding(row) for row in rows]

    async def upsert_event(self, event: CalendarEvent) -> CalendarEvent:
        async with self._session_factory() as session:
            row: CalendarEventORM | None = None
            if event.external_id is not None:
                existing = await session.execute(
                    select(CalendarEventORM)
                    .where(CalendarEventORM.owner_id == event.owner_id)
                    .where(CalendarEventORM.external_id == event.external_id)
                )
                row = existing.scalar_one_or_none()
            if row is None:
                row = CalendarEventORM(owner_id=event.owner_id, title=event.title, start_at=event.start_at, end_at=event.end_at)
                session.add(row)
            row.binding_id = event.binding_id
            row.external_id = event.external_id
            row.title = event.title
            row.start_at = event.start_at
            row.end_at = event.end_at
            row.all_day = event.all_day
            row.location = event.location
            row.description = event.description
            row.source = event.source
            await session.commit()
            await session.refresh(row)
            return _to_calendar_event(row)

    async def list_events(self, owner_id: int, start: datetime, end: datetime) -> list[CalendarEvent]:
        stmt = (
            select(CalendarEventORM)
            .where(CalendarEventORM.owner_id == owner_id)
            .where(CalendarEventORM.start_at < end)
            .where(CalendarEventORM.end_at > start)
            .order_by(CalendarEventORM.start_at.asc(), CalendarEventORM.id.asc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = list(result.scalars().all())
        return [_to_calendar_event(row) for row in rows]


class SqlAlchemyNoteLinkRepository(NoteLinkRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add_link(self, link: NoteLink) -> NoteLink:
        async with self._session_factory() as session:
            row = NoteLinkORM(
                owner_id=link.owner_id,
                note_path=link.note_path,
                note_title=link.note_title,
                relation=link.relation,
                planning_item_id=link.planning_item_id,
                reminder_id=link.reminder_id,
                habit_id=link.habit_id,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _to_note_link(row)

    async def list_links(self, owner_id: int, *, planning_item_id: int | None = None) -> list[NoteLink]:
        stmt = select(NoteLinkORM).where(NoteLinkORM.owner_id == owner_id)
        if planning_item_id is not None:
            stmt = stmt.where(NoteLinkORM.planning_item_id == planning_item_id)
        stmt = stmt.order_by(NoteLinkORM.id.asc())
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = list(result.scalars().all())
        return [_to_note_link(row) for row in rows]
