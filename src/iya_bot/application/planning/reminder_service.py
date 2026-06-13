from __future__ import annotations

from datetime import datetime, timedelta

from iya_bot.application.ports import NotificationProvider, ReminderRepository
from iya_bot.domain.enums import HabitCadence, ReminderKind
from iya_bot.domain.models import Reminder


class ReminderService:
    """Планирование, отмена и срабатывание напоминаний.

    Поддерживает разовые, повторяющиеся напоминания и подталкивания привычек
    (habit_nudge). Доставка идёт через NotificationProvider; реальная отправка в
    Telegram появится, когда порт подключат к aiogram-адаптеру.
    """

    def __init__(self, reminders: ReminderRepository, notifications: NotificationProvider) -> None:
        self._reminders = reminders
        self._notifications = notifications

    async def schedule(
        self,
        owner_id: int,
        chat_id: int,
        text: str,
        due_at: datetime,
        *,
        kind: str = ReminderKind.ONE_OFF,
        recurrence_rule: str | None = None,
        habit_id: int | None = None,
    ) -> Reminder:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("Текст напоминания пустой.")
        reminder = Reminder(
            id=0,
            owner_id=owner_id,
            chat_id=chat_id,
            text=cleaned,
            due_at=due_at,
            status="pending",
            kind=kind,
            recurrence_rule=recurrence_rule,
            habit_id=habit_id,
        )
        return await self._reminders.add_reminder(reminder)

    async def cancel(self, owner_id: int, reminder_id: int) -> bool:
        return await self._reminders.cancel(owner_id, reminder_id)

    async def list_pending(self, owner_id: int, limit: int = 100) -> list[Reminder]:
        return await self._reminders.list_for_owner(owner_id, include_done=False, limit=limit)

    async def fire_due(self, now: datetime, limit: int = 50) -> int:
        """Доставить наступившие напоминания. Повторяющиеся — перепланировать.

        Возвращает число доставленных напоминаний.
        """
        due = await self._reminders.list_due(now, limit=limit)
        delivered = 0
        for reminder in due:
            await self._notifications.notify(reminder.owner_id, reminder.chat_id, reminder.text)
            await self._reminders.mark_sent(reminder.id)
            delivered += 1
            next_due = next_occurrence(reminder, now)
            if next_due is not None:
                await self._reminders.add_reminder(
                    Reminder(
                        id=0,
                        owner_id=reminder.owner_id,
                        chat_id=reminder.chat_id,
                        text=reminder.text,
                        due_at=next_due,
                        status="pending",
                        kind=reminder.kind,
                        recurrence_rule=reminder.recurrence_rule,
                        habit_id=reminder.habit_id,
                    )
                )
        return delivered


def next_occurrence(reminder: Reminder, after: datetime) -> datetime | None:
    """Следующее срабатывание повторяющегося напоминания, либо None для разового.

    Простая модель повторений: recurrence_rule понимает значения HabitCadence
    (daily/weekly/monthly). Разовые напоминания (one_off) не повторяются.
    Реальный iCalendar RRULE-парсинг подключается позже без смены контракта.
    """
    if reminder.kind == ReminderKind.ONE_OFF:
        return None
    rule = (reminder.recurrence_rule or HabitCadence.DAILY).strip().lower()
    delta = _CADENCE_DELTA.get(rule)
    if delta is None:
        return None
    base = reminder.due_at
    nxt = base + delta
    # Не отставать: догоняем до момента строго позже `after`.
    while nxt <= after:
        nxt = nxt + delta
    return nxt


_CADENCE_DELTA = {
    HabitCadence.DAILY: timedelta(days=1),
    HabitCadence.WEEKLY: timedelta(weeks=1),
    HabitCadence.MONTHLY: timedelta(days=30),
}
