"""In-memory fake-репозитории для тестов planning-подсистемы (без БД)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from itertools import count

from iya_bot.domain.models import (
    CalendarBinding,
    CalendarEvent,
    Habit,
    HabitCompletion,
    NoteLink,
    PlanningItem,
    Reminder,
)


class FakePlanningRepo:
    def __init__(self) -> None:
        self.items: list[PlanningItem] = []
        self._ids = count(1)

    async def add_item(self, item: PlanningItem) -> PlanningItem:
        stored = replace(item, id=next(self._ids))
        self.items.append(stored)
        return stored

    async def list_items(self, owner_id: int, *, include_done: bool = False, limit: int = 100) -> list[PlanningItem]:
        result = [i for i in self.items if i.owner_id == owner_id]
        if not include_done:
            result = [i for i in result if i.status not in ("done", "cancelled")]
        return result[:limit]

    async def update_status(self, owner_id: int, item_id: int, status: str) -> bool:
        for index, item in enumerate(self.items):
            if item.owner_id == owner_id and item.id == item_id:
                self.items[index] = replace(item, status=status)
                return True
        return False


class FakeReminderRepo:
    def __init__(self) -> None:
        self.reminders: list[Reminder] = []
        self._ids = count(1)

    async def add_reminder(self, reminder: Reminder) -> Reminder:
        stored = replace(reminder, id=next(self._ids))
        self.reminders.append(stored)
        return stored

    async def list_due(self, now: datetime, limit: int = 50) -> list[Reminder]:
        due = [r for r in self.reminders if r.status == "pending" and r.due_at <= now]
        return sorted(due, key=lambda r: r.due_at)[:limit]

    async def list_for_owner(self, owner_id: int, *, include_done: bool = False, limit: int = 100) -> list[Reminder]:
        result = [r for r in self.reminders if r.owner_id == owner_id]
        if not include_done:
            result = [r for r in result if r.status == "pending"]
        return result[:limit]

    async def mark_sent(self, reminder_id: int) -> None:
        for index, reminder in enumerate(self.reminders):
            if reminder.id == reminder_id:
                self.reminders[index] = replace(reminder, status="sent")

    async def cancel(self, owner_id: int, reminder_id: int) -> bool:
        for index, reminder in enumerate(self.reminders):
            if reminder.owner_id == owner_id and reminder.id == reminder_id and reminder.status == "pending":
                self.reminders[index] = replace(reminder, status="cancelled")
                return True
        return False


class FakeHabitRepo:
    def __init__(self) -> None:
        self.habits: list[Habit] = []
        self.completions: list[HabitCompletion] = []
        self._habit_ids = count(1)
        self._completion_ids = count(1)

    async def add_habit(self, habit: Habit) -> Habit:
        stored = replace(habit, id=next(self._habit_ids))
        self.habits.append(stored)
        return stored

    async def list_habits(self, owner_id: int, *, include_archived: bool = False, limit: int = 100) -> list[Habit]:
        result = [h for h in self.habits if h.owner_id == owner_id]
        if not include_archived:
            result = [h for h in result if h.status != "archived"]
        return result[:limit]

    async def add_completion(self, completion: HabitCompletion) -> HabitCompletion:
        stored = replace(completion, id=next(self._completion_ids))
        self.completions.append(stored)
        return stored

    async def add_completion_for(self, habit_id: int, when: datetime) -> HabitCompletion:
        """Тестовый хелпер: добавить выполнение привычки на момент `when`."""
        return await self.add_completion(HabitCompletion(id=0, habit_id=habit_id, completed_at=when))

    async def list_completions(self, habit_id: int, limit: int = 365) -> list[HabitCompletion]:
        result = [c for c in self.completions if c.habit_id == habit_id]
        return sorted(result, key=lambda c: c.completed_at, reverse=True)[:limit]

    async def update_streak(self, habit_id: int, current_streak: int, last_completed_at: datetime) -> None:
        for index, habit in enumerate(self.habits):
            if habit.id == habit_id:
                self.habits[index] = replace(habit, current_streak=current_streak, last_completed_at=last_completed_at)


class FakeCalendarRepo:
    def __init__(self) -> None:
        self.bindings: list[CalendarBinding] = []
        self.events: list[CalendarEvent] = []
        self._binding_ids = count(1)
        self._event_ids = count(1)

    async def add_binding(self, binding: CalendarBinding) -> CalendarBinding:
        stored = replace(binding, id=next(self._binding_ids))
        self.bindings.append(stored)
        return stored

    async def list_bindings(self, owner_id: int) -> list[CalendarBinding]:
        return [b for b in self.bindings if b.owner_id == owner_id]

    async def upsert_event(self, event: CalendarEvent) -> CalendarEvent:
        for index, existing in enumerate(self.events):
            if event.external_id is not None and existing.external_id == event.external_id and existing.owner_id == event.owner_id:
                self.events[index] = event
                return event
        stored = event if event.id is not None else replace(event, id=next(self._event_ids))
        self.events.append(stored)
        return stored

    async def list_events(self, owner_id: int, start: datetime, end: datetime) -> list[CalendarEvent]:
        return [e for e in self.events if e.owner_id == owner_id and e.start_at < end and e.end_at > start]


class FakeNoteLinkRepo:
    def __init__(self) -> None:
        self.links: list[NoteLink] = []
        self._ids = count(1)

    async def add_link(self, link: NoteLink) -> NoteLink:
        stored = replace(link, id=next(self._ids))
        self.links.append(stored)
        return stored

    async def list_links(self, owner_id: int, *, planning_item_id: int | None = None) -> list[NoteLink]:
        result = [l for l in self.links if l.owner_id == owner_id]
        if planning_item_id is not None:
            result = [l for l in result if l.planning_item_id == planning_item_id]
        return result
