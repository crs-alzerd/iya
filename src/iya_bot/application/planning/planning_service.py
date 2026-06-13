from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from iya_bot.application.planning.calendar_service import CalendarService, FreeSlot
from iya_bot.application.planning.notes_service import NotesService
from iya_bot.application.planning.reminder_service import ReminderService
from iya_bot.application.ports import HabitRepository, ModelProvider, PlanningRepository, WorkflowEngine
from iya_bot.domain.enums import HabitCadence, PlanningStatus, ReminderKind
from iya_bot.domain.models import Habit, HabitCompletion, PlanningItem


@dataclass(frozen=True)
class PlanResult:
    """Результат построения плана: корневая задача, подзадачи и краткое резюме."""

    parent: PlanningItem
    items: list[PlanningItem]
    summary: str | None = None


class PlanningService:
    """Оркестратор planning-подсистемы.

    Превращает цель в дерево задач (через WorkflowEngine), раскладывает их по
    свободным слотам календаря (через CalendarService), ведёт привычки и их
    streak, и координирует напоминания (через ReminderService). ModelProvider
    используется для краткого человекочитаемого резюме плана.
    """

    def __init__(
        self,
        planning: PlanningRepository,
        habits: HabitRepository,
        workflow: WorkflowEngine,
        *,
        model: ModelProvider | None = None,
        calendar: CalendarService | None = None,
        reminders: ReminderService | None = None,
        notes: NotesService | None = None,
    ) -> None:
        self._planning = planning
        self._habits = habits
        self._workflow = workflow
        self._model = model
        self._calendar = calendar
        self._reminders = reminders
        self._notes = notes

    async def create_plan(
        self,
        owner_id: int,
        goal: str,
        *,
        priority: str = "normal",
        schedule_window: tuple[datetime, datetime] | None = None,
        slot_minutes: int = 60,
    ) -> PlanResult:
        cleaned = goal.strip()
        if not cleaned:
            raise ValueError("Цель плана пустая.")

        steps = await self._workflow.plan(cleaned)

        # Раскладка подзадач по свободным слотам календаря (если задано окно).
        starts: list[datetime | None] = [None] * len(steps)
        if schedule_window is not None and self._calendar is not None:
            window_start, window_end = schedule_window
            slots = await self._calendar.free_slots(owner_id, window_start, window_end, min_minutes=slot_minutes)
            starts = assign_slots(len(steps), slots, slot_minutes)

        parent = await self._planning.add_item(
            PlanningItem(id=0, owner_id=owner_id, title=cleaned, status=PlanningStatus.IN_PROGRESS, priority=priority)
        )
        items: list[PlanningItem] = []
        for step, start in zip(steps, starts):
            item = await self._planning.add_item(
                PlanningItem(
                    id=0,
                    owner_id=owner_id,
                    title=step.title,
                    status=PlanningStatus.TODO,
                    priority=priority,
                    scheduled_for=start,
                    parent_id=parent.id,
                )
            )
            items.append(item)

        summary: str | None = None
        if self._model is not None:
            step_lines = "\n".join(f"- {step.title}" for step in steps)
            summary = (await self._model.generate(f"Кратко сформулируй план по цели «{cleaned}»:\n{step_lines}")).strip() or None

        return PlanResult(parent=parent, items=items, summary=summary)

    async def list_open_items(self, owner_id: int, limit: int = 100) -> list[PlanningItem]:
        return await self._planning.list_items(owner_id, include_done=False, limit=limit)

    async def complete_item(self, owner_id: int, item_id: int) -> bool:
        return await self._planning.update_status(owner_id, item_id, PlanningStatus.DONE)

    async def add_habit(
        self,
        owner_id: int,
        title: str,
        *,
        cadence: str = HabitCadence.DAILY,
        target_per_period: int = 1,
        reminder_enabled: bool = True,
    ) -> Habit:
        cleaned = title.strip()
        if not cleaned:
            raise ValueError("Название привычки пустое.")
        return await self._habits.add_habit(
            Habit(
                id=0,
                owner_id=owner_id,
                title=cleaned,
                cadence=cadence,
                target_per_period=target_per_period,
                reminder_enabled=reminder_enabled,
            )
        )

    async def complete_habit(self, habit: Habit, *, now: datetime) -> int:
        """Отметить выполнение привычки, пересчитать и сохранить streak. Возвращает новый streak."""
        await self._habits.add_completion(HabitCompletion(id=0, habit_id=habit.id, completed_at=now))
        completions = await self._habits.list_completions(habit.id)
        dates = [c.completed_at for c in completions] + [now]
        streak = compute_streak(dates, now=now, cadence=habit.cadence)
        await self._habits.update_streak(habit.id, streak, now)
        return streak

    async def ensure_habit_reminder(self, habit: Habit, chat_id: int, due_at: datetime) -> None:
        """Завести повторяющееся подталкивание для привычки, если включены напоминания."""
        if not habit.reminder_enabled or self._reminders is None:
            return
        await self._reminders.schedule(
            habit.owner_id,
            chat_id,
            f"Привычка: {habit.title}",
            due_at,
            kind=ReminderKind.HABIT_NUDGE,
            recurrence_rule=habit.cadence,
            habit_id=habit.id,
        )


def assign_slots(count: int, slots: list[FreeSlot], slot_minutes: int) -> list[datetime | None]:
    """Разложить count задач по свободным слотам, по slot_minutes каждая.

    В один слот помещается несколько задач подряд. Если слотов не хватает —
    оставшиеся получают None (не запланированы).
    """
    starts: list[datetime | None] = []
    step = timedelta(minutes=slot_minutes)
    remaining = count
    for slot in slots:
        cursor = slot.start
        while remaining > 0 and cursor + step <= slot.end:
            starts.append(cursor)
            cursor += step
            remaining -= 1
        if remaining == 0:
            break
    starts.extend([None] * remaining)
    return starts


def compute_streak(completions: list[datetime], *, now: datetime, cadence: str = HabitCadence.DAILY) -> int:
    """Длина непрерывной серии выполнений привычки до текущего периода включительно.

    Период определяется cadence (день/неделя/месяц). Серия считается, если самое
    свежее выполнение пришлось на текущий период или ровно на предыдущий; пропуск
    периода обнуляет серию. Чистая функция — её удобно тестировать.
    """
    if not completions:
        return 0
    buckets = sorted({_bucket(dt, cadence) for dt in completions}, reverse=True)
    current = _bucket(now, cadence)
    if buckets[0] == current:
        expected = current
    elif buckets[0] == current - 1:
        expected = current - 1
    else:
        return 0
    streak = 0
    for bucket in buckets:
        if bucket == expected:
            streak += 1
            expected -= 1
        elif bucket < expected:
            break
    return streak


def _bucket(value: datetime | date, cadence: str) -> int:
    """Нормировать момент в целочисленный номер периода (соседние периоды — соседние int)."""
    day = value.date() if isinstance(value, datetime) else value
    if cadence == HabitCadence.WEEKLY:
        return day.toordinal() // 7
    if cadence == HabitCadence.MONTHLY:
        return day.year * 12 + (day.month - 1)
    return day.toordinal()
