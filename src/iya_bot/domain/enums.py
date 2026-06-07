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


class LLMRequestStatus:
    SUCCESS = "success"
    FAILED = "failed"
