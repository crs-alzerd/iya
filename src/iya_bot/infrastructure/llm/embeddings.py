from __future__ import annotations

import logging

import httpx

from iya_bot.application.ports import EmbeddingClient

logger = logging.getLogger(__name__)


class OpenAICompatibleEmbeddingClient(EmbeddingClient):
    """OpenAI-compatible /embeddings. Эмбеддинги храним как JSON-список float'ов,
    ранжируем косинусом в Python — на объёмах per-user памяти pgvector не нужен."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "text-embedding-3-small",
        timeout_seconds: int = 30,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = await self._client.post(
            f"{self._base_url}/embeddings",
            json={"model": self._model, "input": texts},
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        response.raise_for_status()
        data = response.json()
        items = data.get("data")
        if not isinstance(items, list) or len(items) != len(texts):
            raise RuntimeError(f"Unexpected embeddings response: {str(data)[:500]}")
        # API может вернуть элементы не по порядку — сортируем по index.
        ordered = sorted(items, key=lambda item: item.get("index", 0))
        return [list(map(float, item["embedding"])) for item in ordered]
