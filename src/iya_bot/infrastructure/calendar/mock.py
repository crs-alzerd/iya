from __future__ import annotations

from datetime import datetime
from itertools import count

from iya_bot.application.ports import CalendarProvider
from iya_bot.domain.enums import CalendarProviderKind
from iya_bot.domain.models import CalendarEvent


class InMemoryCalendarProvider(CalendarProvider):
    """Mock-календарь в памяти процесса.

    Замена реального CalDAV/Google/ICS-адаптера на время сборки фундамента.
    Хранит события по owner_id, выдаёт пересечения с запрошенным диапазоном.
    """

    def __init__(self, events: list[CalendarEvent] | None = None) -> None:
        self._events: dict[int, list[CalendarEvent]] = {}
        self._external_ids = count(1)
        for event in events or []:
            self._events.setdefault(event.owner_id, []).append(event)

    async def list_events(self, owner_id: int, start: datetime, end: datetime) -> list[CalendarEvent]:
        owner_events = self._events.get(owner_id, [])
        # Событие попадает в окно, если пересекается с [start, end).
        overlapping = [event for event in owner_events if event.start_at < end and event.end_at > start]
        return sorted(overlapping, key=lambda event: event.start_at)

    async def create_event(self, event: CalendarEvent) -> CalendarEvent:
        external_id = event.external_id or f"mock-{next(self._external_ids)}"
        stored = CalendarEvent(
            id=event.id,
            owner_id=event.owner_id,
            title=event.title,
            start_at=event.start_at,
            end_at=event.end_at,
            binding_id=event.binding_id,
            external_id=external_id,
            all_day=event.all_day,
            location=event.location,
            description=event.description,
            source=CalendarProviderKind.MOCK,
        )
        self._events.setdefault(event.owner_id, []).append(stored)
        return stored

    async def update_event(self, event: CalendarEvent) -> CalendarEvent:
        owner_events = self._events.setdefault(event.owner_id, [])
        for index, existing in enumerate(owner_events):
            if existing.external_id == event.external_id:
                owner_events[index] = event
                return event
        owner_events.append(event)
        return event

    async def delete_event(self, owner_id: int, external_id: str) -> bool:
        owner_events = self._events.get(owner_id, [])
        remaining = [event for event in owner_events if event.external_id != external_id]
        if len(remaining) == len(owner_events):
            return False
        self._events[owner_id] = remaining
        return True
