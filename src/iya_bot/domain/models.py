from dataclasses import dataclass
from datetime import datetime
from typing import Any


ChatContent = str | list[dict[str, Any]]


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: ChatContent


@dataclass(frozen=True)
class ReminderDraft:
    chat_id: int
    telegram_user_id: int
    text: str
    due_at: datetime
