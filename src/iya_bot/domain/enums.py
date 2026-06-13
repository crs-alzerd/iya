class MemoryAuthor:
    USER = "user"
    IYA = "iya"
    EXTRACTED = "extracted"


class MemorySource:
    MANUAL = "manual"
    EXTRACTED = "extracted"
    INFERRED = "inferred"
    REFLECTION = "reflection"


class MemoryStatus:
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class RouteProfile:
    TECHNICAL = "technical"
    PERSONAL = "personal"
    SUPPORT = "support"
    RP = "rp"
    ADMIN = "admin"
    REMINDER = "reminder"
    IMAGE = "image"
    RESEARCH = "research"
    CRISIS = "crisis"
    DEFAULT = "default"


class LLMRequestKind:
    DIALOGUE = "dialogue"
    SUMMARY = "summary"
    REFLECTION = "reflection"
    PROACTIVE = "proactive"
    VISION = "vision"
    CODE = "code"
    ROUTER = "router"
    MEMORY = "memory"


class LLMRequestStatus:
    SUCCESS = "success"
    FAILED = "failed"


# === Planning-система (Obsidian + календарь + планы/привычки) ===
# Строковые значения хранятся в БД и валидируются CheckConstraint'ами в миграции
# 0004. Держим их единым набором, чтобы код и схема не разъезжались.


class PlanningStatus:
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class PlanPriority:
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ReminderStatus:
    PENDING = "pending"
    SENT = "sent"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ReminderKind:
    ONE_OFF = "one_off"
    RECURRING = "recurring"
    HABIT_NUDGE = "habit_nudge"


class HabitCadence:
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class HabitStatus:
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class CalendarProviderKind:
    MOCK = "mock"
    CALDAV = "caldav"
    GOOGLE = "google"
    ICS = "ics"


class CalendarBindingStatus:
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


class NoteRelation:
    SOURCE = "source"
    PLAN = "plan"
    LOG = "log"
    REFERENCE = "reference"


class WorkflowStepStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
