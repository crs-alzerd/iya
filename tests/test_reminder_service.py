from datetime import UTC, datetime, timedelta

from iya_bot.application.planning.reminder_service import ReminderService, next_occurrence
from iya_bot.domain.enums import HabitCadence, ReminderKind
from iya_bot.domain.models import Reminder
from iya_bot.infrastructure.notifications.mock import CollectingNotificationProvider
from planning_fakes import FakeReminderRepo

NOW = datetime(2026, 6, 13, 12, tzinfo=UTC)


async def test_schedule_rejects_empty_text():
    service = ReminderService(FakeReminderRepo(), CollectingNotificationProvider())
    try:
        await service.schedule(1, 100, "  ", NOW)
    except ValueError:
        pass
    else:
        raise AssertionError("ожидалась ValueError на пустой текст")


async def test_fire_due_delivers_and_marks_sent():
    repo = FakeReminderRepo()
    notifier = CollectingNotificationProvider()
    service = ReminderService(repo, notifier)
    await service.schedule(1, 100, "Позвонить врачу", NOW - timedelta(minutes=5))
    await service.schedule(1, 100, "Будущее", NOW + timedelta(hours=2))

    delivered = await service.fire_due(NOW)

    assert delivered == 1
    assert [n.text for n in notifier.sent] == ["Позвонить врачу"]
    pending = await service.list_pending(1)
    assert [r.text for r in pending] == ["Будущее"]


async def test_recurring_reminder_reschedules_next():
    repo = FakeReminderRepo()
    service = ReminderService(repo, CollectingNotificationProvider())
    await service.schedule(
        1, 100, "Зарядка", NOW - timedelta(minutes=1), kind=ReminderKind.HABIT_NUDGE, recurrence_rule=HabitCadence.DAILY
    )

    await service.fire_due(NOW)

    pending = await service.list_pending(1)
    assert len(pending) == 1
    assert pending[0].text == "Зарядка"
    assert pending[0].due_at > NOW


async def test_cancel_pending_reminder():
    repo = FakeReminderRepo()
    service = ReminderService(repo, CollectingNotificationProvider())
    reminder = await service.schedule(1, 100, "Отменяемое", NOW + timedelta(days=1))

    ok = await service.cancel(1, reminder.id)

    assert ok is True
    assert await service.list_pending(1) == []


def test_next_occurrence_one_off_is_none():
    reminder = Reminder(id=1, owner_id=1, chat_id=1, text="x", due_at=NOW, kind=ReminderKind.ONE_OFF)
    assert next_occurrence(reminder, NOW) is None


def test_next_occurrence_weekly_catches_up_past_due():
    reminder = Reminder(
        id=1,
        owner_id=1,
        chat_id=1,
        text="x",
        due_at=NOW - timedelta(weeks=3),
        kind=ReminderKind.RECURRING,
        recurrence_rule=HabitCadence.WEEKLY,
    )
    nxt = next_occurrence(reminder, NOW)
    assert nxt is not None and nxt > NOW
