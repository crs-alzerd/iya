<<<<<<< HEAD
from typing import Sequence
=======
from dataclasses import dataclass
from typing import Any, Sequence
>>>>>>> 1917e25 (Rebuilt full)

import httpx

from iya_bot.application.ports import LLMClient
from iya_bot.domain.models import ChatMessage


<<<<<<< HEAD
=======
@dataclass(frozen=True)
class LLMSamplingParams:
    """Параметры сэмплинга для OpenAI-compatible бэкенда.

    Penalty-параметры и max_tokens опциональны: они кладутся в payload
    только если заданы. Это важно, потому что не каждый провайдер
    (например, отдельные модели в NanoGPT) принимает их одинаково,
    и лишний парашютный параметр может уронить запрос.
    """

    temperature: float = 0.85
    top_p: float | None = None
    presence_penalty: float | None = 0.4
    frequency_penalty: float | None = 0.5
    max_tokens: int | None = None


>>>>>>> 1917e25 (Rebuilt full)
class OpenAICompatibleClient(LLMClient):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 60,
<<<<<<< HEAD
=======
        sampling: LLMSamplingParams | None = None,
>>>>>>> 1917e25 (Rebuilt full)
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
<<<<<<< HEAD

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        url = f"{self._base_url}/chat/completions"
        payload = {
=======
        self._sampling = sampling or LLMSamplingParams()

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        url = f"{self._base_url}/chat/completions"
        payload: dict[str, Any] = {
>>>>>>> 1917e25 (Rebuilt full)
            "model": self._model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
<<<<<<< HEAD
            "temperature": 0.7,
        }
=======
            "temperature": self._sampling.temperature,
        }
        # Кладём опциональные параметры только если они заданы, чтобы
        # не ломать совместимость с разными бэкендами.
        if self._sampling.top_p is not None:
            payload["top_p"] = self._sampling.top_p
        if self._sampling.presence_penalty is not None:
            payload["presence_penalty"] = self._sampling.presence_penalty
        if self._sampling.frequency_penalty is not None:
            payload["frequency_penalty"] = self._sampling.frequency_penalty
        if self._sampling.max_tokens is not None:
            payload["max_tokens"] = self._sampling.max_tokens

>>>>>>> 1917e25 (Rebuilt full)
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
