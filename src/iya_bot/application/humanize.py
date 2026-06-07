from __future__ import annotations

import re

TELEGRAM_MAX_LEN = 4096


def split_into_messages(text: str, max_chunks: int = 3) -> list[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]
    if not paragraphs:
        paragraphs = [cleaned]
    if max_chunks <= 1:
        return _enforce_length([cleaned])
    chunks = _merge_to_limit(paragraphs, max_chunks)
    return _enforce_length(chunks)


def _merge_to_limit(parts: list[str], max_chunks: int) -> list[str]:
    if len(parts) <= max_chunks:
        return parts
    merged = list(parts)
    while len(merged) > max_chunks:
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
    result: list[str] = []
    for chunk in chunks:
        if len(chunk) <= TELEGRAM_MAX_LEN:
            result.append(chunk)
            continue
        result.extend(_hard_split(chunk, TELEGRAM_MAX_LEN))
    return [c for c in result if c.strip()]


def _hard_split(text: str, limit: int) -> list[str]:
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
            for start in range(0, len(sentence), limit):
                pieces.append(sentence[start : start + limit])
            buffer = ""
    if buffer:
        pieces.append(buffer)
    return pieces


def typing_delay_seconds(chunk: str, ms_per_char: int = 22, min_seconds: float = 0.6, max_seconds: float = 4.0) -> float:
    seconds = (len(chunk) * ms_per_char) / 1000.0
    return max(min_seconds, min(max_seconds, seconds))
