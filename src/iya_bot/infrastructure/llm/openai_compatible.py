from typing import Sequence

import httpx

from iya_bot.application.ports import LLMClient
from iya_bot.domain.models import ChatMessage


class OpenAICompatibleClient(LLMClient):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 60,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self._model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "temperature": 0.7,
        }
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
