from __future__ import annotations

from dataclasses import dataclass

from iya_bot.application.ports import NotificationProvider


@dataclass(frozen=True)
class SentNotification:
    owner_id: int
    chat_id: int
    text: str


class CollectingNotificationProvider(NotificationProvider):
    """Mock-доставка: копит отправленное в список вместо реальной отправки.

    Замена реального адаптера поверх aiogram Bot на время сборки фундамента.
    Удобно для тестов: после вызова сервиса проверяем `.sent`.
    """

    def __init__(self) -> None:
        self.sent: list[SentNotification] = []

    async def notify(self, owner_id: int, chat_id: int, text: str) -> None:
        self.sent.append(SentNotification(owner_id=owner_id, chat_id=chat_id, text=text))
