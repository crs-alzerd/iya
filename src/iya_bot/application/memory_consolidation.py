from __future__ import annotations

import json

from iya_bot.domain.models import ChatMessage

# Пер-ход консолидация долговременной памяти. Идея: один фоновый LLM-вызов после
# обмена и обновляет выжимку, и (если включена авто-память) извлекает новые
# устойчивые факты — вместо двух отдельных запросов с почти одинаковым контекстом.

_SUMMARY_ONLY_SYSTEM = (
    "Ты обновляешь долговременную память ассистента по диалогу. "
    "На входе есть прежняя выжимка и новый обмен сообщениями. "
    "Верни только новую краткую выжимку без вступлений, markdown-заголовков и служебных комментариев. "
    "Сохраняй устойчивые факты о пользователе, проекте, предпочтениях, решениях, открытых задачах и важном контексте. "
    "Удаляй временный шум, повторы и устаревшие детали. Максимум 2500 символов."
)

_CONSOLIDATION_SYSTEM = (
    "Ты обновляешь долговременную память ассистента после одного обмена сообщениями. "
    "Нужно сделать две вещи за один проход:\n"
    "1) summary — обновлённая краткая выжимка диалога (до 2500 символов): устойчивые факты о пользователе, "
    "проекте, предпочтениях, решениях, открытых задачах; без шума, повторов и устаревшего.\n"
    "2) new_facts — список НОВЫХ устойчивых фактов о пользователе или общих делах, которых ещё нет в списке "
    "известных. Каждый факт — короткая самодостаточная фраза от третьего лица. Не дублируй известные факты, "
    "не добавляй сиюминутный шум, эмоции момента, вопросы и домыслы. Если новых фактов нет — пустой список.\n"
    "Верни только JSON без markdown."
)


def build_summary_messages(
    previous_summary: str | None, user_text: str, assistant_text: str
) -> list[ChatMessage]:
    return [
        ChatMessage(role="system", content=_SUMMARY_ONLY_SYSTEM),
        ChatMessage(
            role="user",
            content=(
                "Прежняя выжимка:\n"
                f"{previous_summary or 'Пока нет.'}\n\n"
                "Новый обмен:\n"
                f"Пользователь: {user_text}\n"
                f"Ассистент: {assistant_text}\n\n"
                "Обновлённая выжимка:"
            ),
        ),
    ]


def build_consolidation_messages(
    previous_summary: str | None,
    existing_facts: list[str],
    user_text: str,
    assistant_text: str,
) -> list[ChatMessage]:
    return [
        ChatMessage(role="system", content=_CONSOLIDATION_SYSTEM),
        ChatMessage(
            role="user",
            content=(
                "Прежняя выжимка:\n"
                f"{previous_summary or 'Пока нет.'}\n\n"
                "Уже известные факты (не дублируй их в new_facts):\n"
                f"{json.dumps(existing_facts, ensure_ascii=False)}\n\n"
                "Новый обмен:\n"
                f"Пользователь: {user_text}\n"
                f"Ия: {assistant_text}\n\n"
                'Верни JSON строго вида: {"summary": "…", "new_facts": ["факт", "факт"]}'
            ),
        ),
    ]


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def parse_consolidation(raw: str) -> tuple[str, list[str]]:
    """Разобрать JSON-ответ консолидации в (summary, new_facts). Толерантно к мусору."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return "", []
    if not isinstance(data, dict):
        return "", []
    summary = data.get("summary")
    summary = summary.strip()[:2500] if isinstance(summary, str) else ""
    facts = _clean_facts(data.get("new_facts"))
    return summary, facts


def _clean_facts(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        fact = item.strip()
        key = normalize(fact)
        if not fact or key in seen:
            continue
        seen.add(key)
        result.append(fact[:500])
    return result
