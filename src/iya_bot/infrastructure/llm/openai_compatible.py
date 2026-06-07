from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import httpx

from iya_bot.application.ports import LLMClient
from iya_bot.domain.models import ChatMessage


@dataclass(frozen=True)
class LLMSamplingParams:
    temperature: float = 0.85
    top_p: float | None = None
    presence_penalty: float | None = 0.4
    frequency_penalty: float | None = 0.5
    max_tokens: int | None = None


class OpenAICompatibleClient(LLMClient):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 60,
        sampling: LLMSamplingParams | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._sampling = sampling or LLMSamplingParams()

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        kind: str = "dialogue",
        telegram_user_id: int | None = None,
    ) -> str:
        url = f"{self._base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": message.role, "content": message.content} for message in messages],
            "temperature": self._sampling.temperature,
        }
        if self._sampling.top_p is not None:
            payload["top_p"] = self._sampling.top_p
        if self._sampling.presence_penalty is not None:
            payload["presence_penalty"] = self._sampling.presence_penalty
        if self._sampling.frequency_penalty is not None:
            payload["frequency_penalty"] = self._sampling.frequency_penalty
        if self._sampling.max_tokens is not None:
            payload["max_tokens"] = self._sampling.max_tokens

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected LLM response format: {data!r}") from exc

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("LLM returned empty response.")
        return content.strip()
