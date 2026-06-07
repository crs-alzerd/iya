import logging

from aiogram import Bot

from iya_bot.application.proactive import PROACTIVE_KIND_CHECK_IN, ProactiveService
from iya_bot.infrastructure.db.repositories import ProactiveEventDueRepository

logger = logging.getLogger(__name__)


class ProactiveJobRunner:
    def __init__(
        self,
        bot: Bot,
        due_repository: ProactiveEventDueRepository,
        proactive: ProactiveService,
    ) -> None:
        self._bot = bot
        self._due_repository = due_repository
        self._proactive = proactive
        self._locked = False

    async def send_due_events(self) -> None:
        if self._locked:
            return

        self._locked = True
        try:
            events = await self._due_repository.get_due_pending(limit=10)
            for event in events:
                try:
                    if event.kind != PROACTIVE_KIND_CHECK_IN:
                        await self._due_repository.mark_failed(event.id)
                        continue

                    text = await self._proactive.generate_check_in(event.telegram_user_id)
                    await self._bot.send_message(chat_id=event.chat_id, text=text)
                    await self._proactive.record_sent_check_in(
                        telegram_user_id=event.telegram_user_id,
                        text=text,
                    )
                    await self._due_repository.mark_sent(event.id)
                    await self._proactive.ensure_next_check_in(
                        telegram_user_id=event.telegram_user_id,
                        chat_id=event.chat_id,
                    )
                except Exception:
                    logger.exception("Failed to send proactive event id=%s", event.id)
                    await self._due_repository.mark_failed(event.id)
        finally:
            self._locked = False
