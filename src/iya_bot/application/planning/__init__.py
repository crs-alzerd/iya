"""Planning-подсистема Ии: планы, привычки, календарь и заметки Obsidian.

Сервисы зависят только от портов (`application/ports.py`) и доменных моделей,
поэтому бизнес-логику можно тестировать на mock-провайдерах без реальных API.
Подключение к живому диалогу/планировщику — отдельный следующий шаг.
"""

from iya_bot.application.planning.calendar_service import CalendarService, FreeSlot
from iya_bot.application.planning.notes_service import NotesService
from iya_bot.application.planning.planning_service import PlanningService, compute_streak
from iya_bot.application.planning.reminder_service import ReminderService

__all__ = [
    "CalendarService",
    "FreeSlot",
    "NotesService",
    "PlanningService",
    "ReminderService",
    "compute_streak",
]
