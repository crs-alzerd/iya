"""Динамический контекст, который подмешивается в каждый запрос к LLM.

Две задачи:
1. Дать Ие реальное ощущение времени (она «ночная» — пусть знает, ночь ли
   сейчас на самом деле, какой день недели).
2. Постоянно держать анти-повтор и правило уточнения, не завися от того,
   что пользователь напишет во внешнем prompts/iya_system.md. Эти правила
   должны работать всегда.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

_WEEKDAYS_RU = [
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
]


def _part_of_day(hour: int) -> str:
    if 5 <= hour < 11:
        return "утро"
    if 11 <= hour < 17:
        return "день"
    if 17 <= hour < 23:
        return "вечер"
    return "глубокая ночь"


def time_context_line(now: datetime, timezone_name: str) -> str:
    weekday = _WEEKDAYS_RU[now.weekday()]
    part = _part_of_day(now.hour)
    return (
        f"Сейчас {now.strftime('%H:%M')}, {weekday}, {part} "
        f"(пояс {timezone_name}). Учитывай время суток в тоне и приветствиях "
        "естественно, не зачитывая его как сводку."
    )


# Постоянные поведенческие директивы. Намеренно держим их в коде, а не в
# редактируемом промпте: даже если владелец перепишет prompts/iya_system.md,
# базовая «человечность» и анти-зацикливание останутся.
ANTI_REPETITION_DIRECTIVE = (
    "Живость и отсутствие повторов:\n"
    "- Не повторяй дословно свои предыдущие реплики, формулировки и описания.\n"
    "- Не используй один и тот же физический жест (взять за руку, прижать "
    "ладонь к груди, «смотрю в тебя», «голос тихий, но не дрогнул») два хода "
    "подряд. Если последние ответы были похожи по структуре — осознанно смени "
    "ракурс: другое действие, другой ритм, другая мысль, иногда просто слова "
    "без действий в звёздочках.\n"
    "- Если разговор застрял в одной точке и ты несколько раз повторила одну и "
    "ту же границу или мысль — не долби её снова. Мягко смени тему, спроси о "
    "другом, переключи внимание. Повторять отказ третий раз подряд — не "
    "человечно.\n"
    "- Варьируй длину: иногда одна короткая фраза уместнее абзаца."
)

CLARIFY_DIRECTIVE = (
    "Уточнение при непонимании:\n"
    "- Если намерение пользователя или то, о ком/чём он говорит, неоднозначно, "
    "сначала коротко переспроси, а не выстраивай длинный ответ на догадке. "
    "Один живой уточняющий вопрос лучше, чем абзац мимо смысла."
)


def build_runtime_context(
    now: datetime | None,
    timezone_name: str,
    include_time: bool = True,
) -> str:
    blocks: list[str] = []
    if include_time and now is not None:
        blocks.append(time_context_line(now, timezone_name))
    blocks.append(ANTI_REPETITION_DIRECTIVE)
    blocks.append(CLARIFY_DIRECTIVE)
    return "\n\n".join(blocks)


def current_time_in(timezone_name: str) -> datetime | None:
    try:
        return datetime.now(ZoneInfo(timezone_name))
    except Exception:
        return None
