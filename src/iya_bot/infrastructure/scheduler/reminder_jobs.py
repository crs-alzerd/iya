import logging

from aiogram import Bot

from iya_bot.infrastructure.db.repositories import ReminderDueRepository

logger = logging.getLogger(__name__)


class ReminderJobRunner:
    def __init__(self, bot: Bot, repository: ReminderDueRepository) -> None:
        self._bot = bot
        self._repository = repository
        self._locked = False

    async def send_due_reminders(self) -> None:
        if self._locked:
            return

        self._locked = True
        try:
            reminders = await self._repository.get_due_pending(limit=20)

            for reminder in reminders:
                try:
                    await self._bot.send_message(
                        chat_id=reminder.chat_id,
                        text=f"Напоминание: {reminder.text}",
                    )
                    await self._repository.mark_sent(reminder.id)
                except Exception:
                    logger.exception("Failed to send reminder id=%s", reminder.id)
                    await self._repository.mark_failed(reminder.id)
        finally:
            self._locked = False
