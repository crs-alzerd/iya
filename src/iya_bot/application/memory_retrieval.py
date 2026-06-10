from __future__ import annotations

import logging
import math

from iya_bot.application.ports import EmbeddingClient, MemoryRepository
from iya_bot.domain.models import MemoryItem

logger = logging.getLogger(__name__)

# Вес семантической близости против важности факта. Похожесть важнее, но salience
# не даёт совсем потерять закреплённое вручную при нерелевантном запросе.
_SIMILARITY_WEIGHT = 0.75
_SALIENCE_WEIGHT = 0.25


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def rank_by_relevance(query_embedding: list[float], items: list[MemoryItem], top_k: int) -> list[MemoryItem]:
    """Топ-k фактов: с эмбеддингами — по смеси похожести и salience, остальные —
    добивают хвост по salience (пока backfill их не догнал)."""
    embedded = [item for item in items if item.embedding]
    missing = [item for item in items if not item.embedding]

    scored = sorted(
        embedded,
        key=lambda item: (
            _SIMILARITY_WEIGHT * cosine_similarity(query_embedding, item.embedding or [])
            + _SALIENCE_WEIGHT * item.salience_score
        ),
        reverse=True,
    )
    result = scored[:top_k]
    if len(result) < top_k:
        fallback = sorted(missing, key=lambda item: item.salience_score, reverse=True)
        result.extend(fallback[: top_k - len(result)])
    return result


class MemoryRetrievalService:
    """Семантический выбор фактов памяти под текущее сообщение.

    Эмбеддинги хранятся в JSON-колонке memory_facts.embedding и считаются лениво:
    backfill() добивает недостающие после консолидации. Ранжирование в Python —
    объём per-user памяти (десятки–сотни фактов) этого более чем позволяет.
    """

    def __init__(
        self,
        embedder: EmbeddingClient,
        memories: MemoryRepository,
        top_k: int = 20,
        backfill_batch: int = 16,
    ) -> None:
        self._embedder = embedder
        self._memories = memories
        self._top_k = max(1, top_k)
        self._backfill_batch = max(1, backfill_batch)

    async def select_relevant(self, query: str, items: list[MemoryItem]) -> list[MemoryItem]:
        """Выбрать релевантные факты. При любой ошибке эмбеддинга — salience-fallback."""
        if len(items) <= self._top_k:
            return items
        cleaned = query.strip()
        if not cleaned:
            return items[: self._top_k]
        try:
            query_embedding = (await self._embedder.embed([cleaned[:2000]]))[0]
        except Exception:
            logger.exception("Query embedding failed; falling back to salience order")
            return items[: self._top_k]
        return rank_by_relevance(query_embedding, items, self._top_k)

    async def backfill(self, telegram_user_id: int) -> int:
        """Посчитать эмбеддинги фактам, у которых их ещё нет. Возвращает число обновлённых."""
        try:
            pending = await self._memories.list_facts_missing_embedding(
                telegram_user_id, limit=self._backfill_batch
            )
        except Exception:
            logger.exception("Failed to list facts missing embedding for telegram_user_id=%s", telegram_user_id)
            return 0
        if not pending:
            return 0
        try:
            embeddings = await self._embedder.embed([item.text[:2000] for item in pending])
        except Exception:
            logger.exception("Embedding backfill failed for telegram_user_id=%s", telegram_user_id)
            return 0
        updated = 0
        for item, embedding in zip(pending, embeddings):
            try:
                await self._memories.set_fact_embedding(telegram_user_id, item.id, embedding)
                updated += 1
            except Exception:
                logger.exception("Failed to store embedding for fact id=%s", item.id)
        return updated
