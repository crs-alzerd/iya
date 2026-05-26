import re
from datetime import UTC, datetime, timedelta

from iya_bot.application.ports import ReminderRepository


_DURATION_RE = re.compile(r"^\s*(?P<amount>\d+)\s*(?P<unit>[mhd])\s+(?P<text>.+?)\s*$", re.IGNORECASE)


class ReminderParseError(ValueError):
    pass


class ReminderService:
    def __init__(self, reminders: ReminderRepository) -> None:
        self._reminders = reminders

    async def create_from_command(self, telegram_user_id: int, chat_id: int, command_payload: str) -> int:
        due_at, text = parse_reminder_payload(command_payload)
        return await self._reminders.create_reminder(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            text=text,
            due_at=due_at,
        )


def parse_reminder_payload(payload: str) -> tuple[datetime, str]:
    match = _DURATION_RE.match(payload)
    if not match:
        raise ReminderParseError(
            "Формат: /remind 10m текст, /remind 2h текст или /remind 1d текст."
        )

    amount = int(match.group("amount"))
    unit = match.group("unit").lower()
    text = match.group("text").strip()

    if amount <= 0:
        raise ReminderParseError("Интервал должен быть больше нуля.")

    if not text:
        raise ReminderParseError("Текст напоминания не должен быть пустым.")

    now = datetime.now(UTC)

    if unit == "m":
        delta = timedelta(minutes=amount)
    elif unit == "h":
        delta = timedelta(hours=amount)
    elif unit == "d":
        delta = timedelta(days=amount)
    else:
        raise ReminderParseError("Поддерживаются только m, h и d.")

    return now + delta, text
