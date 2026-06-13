from datetime import UTC, datetime

from iya_bot.application.planning.calendar_service import CalendarService
from iya_bot.domain.models import CalendarEvent
from iya_bot.infrastructure.calendar.mock import InMemoryCalendarProvider
from planning_fakes import FakeCalendarRepo


def _event(owner_id: int, h1: int, h2: int, *, all_day: bool = False) -> CalendarEvent:
    return CalendarEvent(
        id=None,
        owner_id=owner_id,
        title=f"event {h1}-{h2}",
        start_at=datetime(2026, 6, 13, h1, tzinfo=UTC),
        end_at=datetime(2026, 6, 13, h2, tzinfo=UTC),
        all_day=all_day,
    )


async def test_list_events_caches_into_repo():
    provider = InMemoryCalendarProvider([_event(1, 10, 11)])
    repo = FakeCalendarRepo()
    service = CalendarService(provider, repo)

    events = await service.list_events(1, datetime(2026, 6, 13, 0, tzinfo=UTC), datetime(2026, 6, 14, 0, tzinfo=UTC))

    assert len(events) == 1
    assert len(repo.events) == 1


async def test_create_event_goes_through_provider_and_cache():
    provider = InMemoryCalendarProvider()
    repo = FakeCalendarRepo()
    service = CalendarService(provider, repo)

    created = await service.create_event(_event(1, 14, 15))

    assert created.external_id is not None
    assert created.source == "mock"
    assert len(repo.events) == 1


async def test_free_slots_skips_busy_intervals():
    provider = InMemoryCalendarProvider([_event(1, 10, 11), _event(1, 13, 14)])
    service = CalendarService(provider)

    day_start = datetime(2026, 6, 13, 9, tzinfo=UTC)
    day_end = datetime(2026, 6, 13, 18, tzinfo=UTC)
    slots = await service.free_slots(1, day_start, day_end, min_minutes=30)

    # Ожидаем: 9-10, 11-13, 14-18.
    spans = [(s.start.hour, s.end.hour) for s in slots]
    assert spans == [(9, 10), (11, 13), (14, 18)]


async def test_free_slots_merges_overlapping_busy():
    provider = InMemoryCalendarProvider([_event(1, 10, 12), _event(1, 11, 13)])
    service = CalendarService(provider)

    slots = await service.free_slots(
        1, datetime(2026, 6, 13, 9, tzinfo=UTC), datetime(2026, 6, 13, 15, tzinfo=UTC), min_minutes=30
    )

    spans = [(s.start.hour, s.end.hour) for s in slots]
    assert spans == [(9, 10), (13, 15)]


async def test_all_day_event_does_not_block_slots():
    provider = InMemoryCalendarProvider([_event(1, 0, 23, all_day=True)])
    service = CalendarService(provider)

    slots = await service.free_slots(
        1, datetime(2026, 6, 13, 9, tzinfo=UTC), datetime(2026, 6, 13, 18, tzinfo=UTC), min_minutes=30
    )

    assert len(slots) == 1
    assert (slots[0].start.hour, slots[0].end.hour) == (9, 18)
