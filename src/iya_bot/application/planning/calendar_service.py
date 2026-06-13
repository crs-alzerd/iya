from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from iya_bot.application.ports import CalendarProvider, CalendarRepository
from iya_bot.domain.models import CalendarEvent


@dataclass(frozen=True)
class FreeSlot:
    """Свободный интервал в расписании владельца."""

    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


class CalendarService:
    """Работа с календарём владельца поверх CalendarProvider.

    События читаются у провайдера, кэшируются в CalendarRepository (для оффлайн-
    доступа и истории) и используются для расчёта занятости/свободных слотов —
    это основа для раскладки планов по расписанию.
    """

    def __init__(self, provider: CalendarProvider, calendar_repo: CalendarRepository | None = None) -> None:
        self._provider = provider
        self._repo = calendar_repo

    async def list_events(self, owner_id: int, start: datetime, end: datetime) -> list[CalendarEvent]:
        events = await self._provider.list_events(owner_id, start, end)
        if self._repo is not None:
            for event in events:
                await self._repo.upsert_event(event)
        return events

    async def create_event(self, event: CalendarEvent) -> CalendarEvent:
        created = await self._provider.create_event(event)
        if self._repo is not None:
            await self._repo.upsert_event(created)
        return created

    async def free_slots(
        self,
        owner_id: int,
        start: datetime,
        end: datetime,
        *,
        min_minutes: int = 30,
    ) -> list[FreeSlot]:
        """Свободные интервалы длиннее min_minutes в окне [start, end)."""
        events = await self.list_events(owner_id, start, end)
        busy = _merge_intervals(
            [(max(event.start_at, start), min(event.end_at, end)) for event in events if not event.all_day]
        )
        slots: list[FreeSlot] = []
        cursor = start
        for busy_start, busy_end in busy:
            if busy_start > cursor:
                slots.append(FreeSlot(start=cursor, end=busy_start))
            cursor = max(cursor, busy_end)
        if cursor < end:
            slots.append(FreeSlot(start=cursor, end=end))
        return [slot for slot in slots if slot.minutes >= min_minutes]

    async def is_busy(self, owner_id: int, start: datetime, end: datetime) -> bool:
        events = await self._provider.list_events(owner_id, start, end)
        return any(event.start_at < end and event.end_at > start and not event.all_day for event in events)


def _merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """Слить пересекающиеся занятые интервалы в непересекающиеся, по возрастанию."""
    cleaned = sorted((s, e) for s, e in intervals if e > s)
    merged: list[tuple[datetime, datetime]] = []
    for start, end in cleaned:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged
