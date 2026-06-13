from datetime import UTC, datetime, timedelta

from iya_bot.application.planning.calendar_service import CalendarService
from iya_bot.application.planning.planning_service import PlanningService, assign_slots, compute_streak
from iya_bot.application.planning.reminder_service import ReminderService
from iya_bot.application.planning.calendar_service import FreeSlot
from iya_bot.domain.enums import HabitCadence, PlanningStatus, ReminderKind
from iya_bot.domain.models import CalendarEvent
from iya_bot.infrastructure.calendar.mock import InMemoryCalendarProvider
from iya_bot.infrastructure.llm.mock_model_provider import CannedModelProvider
from iya_bot.infrastructure.notifications.mock import CollectingNotificationProvider
from iya_bot.infrastructure.workflow.mock import DeterministicWorkflowEngine
from planning_fakes import FakeHabitRepo, FakePlanningRepo, FakeReminderRepo

NOW = datetime(2026, 6, 13, 12, tzinfo=UTC)


def _service(*, calendar=None, reminders=None, model=None, workflow=None):
    return PlanningService(
        planning=FakePlanningRepo(),
        habits=FakeHabitRepo(),
        workflow=workflow or DeterministicWorkflowEngine(template=["A", "B"]),
        model=model,
        calendar=calendar,
        reminders=reminders,
    )


async def test_create_plan_decomposes_goal_into_subitems():
    model = CannedModelProvider(["Короткое резюме плана"])
    service = _service(model=model, workflow=DeterministicWorkflowEngine(template=["Шаг 1", "Шаг 2"]))

    result = await service.create_plan(5, "запустить проект")

    assert result.parent.status == PlanningStatus.IN_PROGRESS
    assert [i.title for i in result.items] == ["Шаг 1: запустить проект", "Шаг 2: запустить проект"]
    assert all(i.parent_id == result.parent.id for i in result.items)
    assert all(i.status == PlanningStatus.TODO for i in result.items)
    assert result.summary == "Короткое резюме плана"


async def test_create_plan_rejects_empty_goal():
    service = _service()
    try:
        await service.create_plan(1, "   ")
    except ValueError:
        pass
    else:
        raise AssertionError("ожидалась ValueError на пустую цель")


async def test_create_plan_schedules_items_around_busy_calendar():
    busy = CalendarEvent(
        id=None,
        owner_id=5,
        title="встреча",
        start_at=datetime(2026, 6, 13, 10, tzinfo=UTC),
        end_at=datetime(2026, 6, 13, 11, tzinfo=UTC),
    )
    calendar = CalendarService(InMemoryCalendarProvider([busy]))
    service = _service(calendar=calendar, workflow=DeterministicWorkflowEngine(template=["A", "B"]))

    window = (datetime(2026, 6, 13, 9, tzinfo=UTC), datetime(2026, 6, 13, 12, tzinfo=UTC))
    result = await service.create_plan(5, "цель", schedule_window=window, slot_minutes=60)

    scheduled = [i.scheduled_for for i in result.items]
    # Свободные слоты 9-10 и 11-12 → две задачи по 60 минут.
    assert scheduled[0] == datetime(2026, 6, 13, 9, tzinfo=UTC)
    assert scheduled[1] == datetime(2026, 6, 13, 11, tzinfo=UTC)


async def test_complete_habit_updates_streak():
    repo = FakeHabitRepo()
    service = PlanningService(planning=FakePlanningRepo(), habits=repo, workflow=DeterministicWorkflowEngine())
    habit = await service.add_habit(1, "медитация", cadence=HabitCadence.DAILY)
    # Два прошлых выполнения — вчера и позавчера.
    await repo.add_completion_for(habit.id, NOW - timedelta(days=2))
    await repo.add_completion_for(habit.id, NOW - timedelta(days=1))

    streak = await service.complete_habit(habit, now=NOW)

    assert streak == 3
    assert repo.habits[0].current_streak == 3


async def test_ensure_habit_reminder_creates_nudge():
    rem_repo = FakeReminderRepo()
    reminders = ReminderService(rem_repo, CollectingNotificationProvider())
    service = _service(reminders=reminders)
    habit = await service.add_habit(1, "вода", cadence=HabitCadence.DAILY)

    await service.ensure_habit_reminder(habit, chat_id=100, due_at=NOW + timedelta(hours=1))

    assert len(rem_repo.reminders) == 1
    nudge = rem_repo.reminders[0]
    assert nudge.kind == ReminderKind.HABIT_NUDGE
    assert nudge.habit_id == habit.id
    assert nudge.recurrence_rule == HabitCadence.DAILY


async def test_ensure_habit_reminder_skips_when_disabled():
    rem_repo = FakeReminderRepo()
    reminders = ReminderService(rem_repo, CollectingNotificationProvider())
    service = _service(reminders=reminders)
    habit = await service.add_habit(1, "чтение", reminder_enabled=False)

    await service.ensure_habit_reminder(habit, chat_id=100, due_at=NOW)

    assert rem_repo.reminders == []


# --- чистые функции ---


def test_assign_slots_packs_multiple_per_slot_and_overflow_none():
    slots = [FreeSlot(datetime(2026, 6, 13, 9, tzinfo=UTC), datetime(2026, 6, 13, 11, tzinfo=UTC))]
    starts = assign_slots(3, slots, slot_minutes=60)
    assert starts[0] == datetime(2026, 6, 13, 9, tzinfo=UTC)
    assert starts[1] == datetime(2026, 6, 13, 10, tzinfo=UTC)
    assert starts[2] is None  # слот вмещает только две задачи по 60 минут


def test_compute_streak_consecutive_days():
    days = [NOW - timedelta(days=2), NOW - timedelta(days=1), NOW]
    assert compute_streak(days, now=NOW, cadence=HabitCadence.DAILY) == 3


def test_compute_streak_breaks_on_gap():
    days = [NOW - timedelta(days=5), NOW - timedelta(days=1), NOW]
    assert compute_streak(days, now=NOW, cadence=HabitCadence.DAILY) == 2


def test_compute_streak_zero_when_stale():
    days = [NOW - timedelta(days=5)]
    assert compute_streak(days, now=NOW, cadence=HabitCadence.DAILY) == 0


def test_compute_streak_weekly():
    weeks = [NOW - timedelta(weeks=2), NOW - timedelta(weeks=1), NOW]
    assert compute_streak(weeks, now=NOW, cadence=HabitCadence.WEEKLY) == 3
