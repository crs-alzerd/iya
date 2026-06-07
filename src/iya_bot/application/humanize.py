"""Превращение монолитного ответа LLM в «человеческую» подачу.

Чистые функции без зависимостей от aiogram, чтобы их можно было
протестировать отдельно. Логика отправки (typing-индикатор, задержки)
живёт в telegram-слое и использует эти функции.
"""
from __future__ import annotations

import re

# Жёсткий лимит Telegram на одно сообщение.
TELEGRAM_MAX_LEN = 4096


def split_into_messages(text: str, max_chunks: int = 3) -> list[str]:
    """Разбить ответ на 1..max_chunks «реплик», как пишет живой человек.

    Принципы:
    - сначала пытаемся резать по пустым строкам (естественные абзацы);
    - если кусков больше, чем max_chunks, лишние склеиваем обратно к
      соседям, чтобы не спамить десятком сообщений;
    - очень длинные куски дополнительно режем по границам предложений,
      не превышая лимит Telegram.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return []

    # Абзацы по пустым строкам.
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]
    if not paragraphs:
        paragraphs = [cleaned]

    # Если max_chunks <= 1 — отдаём одним куском (но всё равно режем по лимиту).
    if max_chunks <= 1:
        return _enforce_length([cleaned])

    # Склеиваем абзацы в не более чем max_chunks групп, балансируя по длине.
    chunks = _merge_to_limit(paragraphs, max_chunks)
    return _enforce_length(chunks)


def _merge_to_limit(parts: list[str], max_chunks: int) -> list[str]:
    if len(parts) <= max_chunks:
        return parts

    # Жадно склеиваем самые короткие соседние куски, пока не уложимся.
    merged = list(parts)
    while len(merged) > max_chunks:
        # Находим пару соседей с минимальной суммарной длиной.
        best_i = 0
        best_len = None
        for i in range(len(merged) - 1):
            combined = len(merged[i]) + len(merged[i + 1])
            if best_len is None or combined < best_len:
                best_len = combined
                best_i = i
        merged[best_i] = (merged[best_i] + "\n\n" + merged[best_i + 1]).strip()
        del merged[best_i + 1]
    return merged


def _enforce_length(chunks: list[str]) -> list[str]:
    """Гарантируем, что ни один кусок не длиннее лимита Telegram."""
    result: list[str] = []
    for chunk in chunks:
        if len(chunk) <= TELEGRAM_MAX_LEN:
            result.append(chunk)
            continue
        result.extend(_hard_split(chunk, TELEGRAM_MAX_LEN))
    return [c for c in result if c.strip()]


def _hard_split(text: str, limit: int) -> list[str]:
    # Режем по предложениям, добивая по словам, в самом крайнем случае — по символам.
    sentences = re.split(r"(?<=[.!?…])\s+", text)
    pieces: list[str] = []
    buffer = ""
    for sentence in sentences:
        candidate = (buffer + " " + sentence).strip() if buffer else sentence
        if len(candidate) <= limit:
            buffer = candidate
            continue
        if buffer:
            pieces.append(buffer)
        if len(sentence) <= limit:
            buffer = sentence
        else:
            # Предложение само длиннее лимита — режем по символам.
            for start in range(0, len(sentence), limit):
                pieces.append(sentence[start : start + limit])
            buffer = ""
    if buffer:
        pieces.append(buffer)
    return pieces


def typing_delay_seconds(
    chunk: str,
    ms_per_char: int = 22,
    min_seconds: float = 0.6,
    max_seconds: float = 4.0,
) -> float:
    """Сколько «печатать» этот кусок, чтобы ритм выглядел живым.

    Пропорционально длине, но с разумными границами: короткое «я тут.»
    не должно висеть 4 секунды, а длинный абзац не должен мелькать мгновенно.
    """
    seconds = (len(chunk) * ms_per_char) / 1000.0
    return max(min_seconds, min(max_seconds, seconds))
