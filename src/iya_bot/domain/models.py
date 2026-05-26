from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ReminderDraft:
    chat_id: int
    telegram_user_id: int
    text: str
    due_at: datetime
