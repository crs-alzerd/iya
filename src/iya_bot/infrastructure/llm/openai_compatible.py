from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, AsyncIterator, Sequence

import httpx

from iya_bot.application.ports import LLMClient
from iya_bot.domain.models import ChatMessage, LLMResponse, ToolCall


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
        # Один клиент на всё время жизни: соединение и TLS-handshake переиспользуются
        # между вызовами (диалог + tool-loop + фоновые консолидации памяти).
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        kind: str = "dialogue",
        telegram_user_id: int | None = None,
    ) -> str:
        payload = self._base_payload(messages)
        data = await self._post(payload)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected LLM response format: {data!r}") from exc

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("LLM returned empty response.")
        return content.strip()

    async def complete_tools(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: list[dict],
        kind: str = "dialogue",
        telegram_user_id: int | None = None,
    ) -> LLMResponse:
        payload = self._base_payload(messages)
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        data = await self._post(payload)
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected LLM response format: {data!r}") from exc

        content = message.get("content")
        content = content.strip() if isinstance(content, str) else None
        tool_calls = tuple(_parse_tool_calls(message.get("tool_calls")))
        if content is None and not tool_calls:
            raise RuntimeError("LLM returned neither content nor tool calls.")
        return LLMResponse(content=content, tool_calls=tool_calls)

    async def complete_stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        kind: str = "dialogue",
        telegram_user_id: int | None = None,
    ) -> AsyncIterator[str]:
        payload = self._base_payload(messages)
        payload["stream"] = True
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with self._client.stream("POST", url, json=payload, headers=headers) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                delta = extract_stream_delta(line)
                if delta:
                    yield delta

    def _base_payload(self, messages: Sequence[ChatMessage]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [_serialize_message(message) for message in messages],
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
        return payload

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        response = await self._client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


def extract_stream_delta(line: str) -> str | None:
    """Достать дельту текста из одной SSE-строки `data: {...}`. Вынесено для юнит-тестов."""
    line = line.strip()
    if not line.startswith("data:"):
        return None
    data = line[5:].strip()
    if not data or data == "[DONE]":
        return None
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError:
        return None
    try:
        delta = parsed["choices"][0].get("delta") or {}
    except (KeyError, IndexError, TypeError):
        return None
    content = delta.get("content")
    return content if isinstance(content, str) and content else None


def _serialize_message(message: ChatMessage) -> dict[str, Any]:
    data: dict[str, Any] = {"role": message.role}
    # assistant с tool_calls может иметь content=null — это валидно для OpenAI.
    if message.content is not None or message.tool_calls:
        data["content"] = message.content
    if message.tool_calls:
        data["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments},
            }
            for call in message.tool_calls
        ]
    if message.tool_call_id is not None:
        data["tool_call_id"] = message.tool_call_id
    if message.name is not None:
        data["name"] = message.name
    return data


def _parse_tool_calls(raw: Any) -> list[ToolCall]:
    if not isinstance(raw, list):
        return []
    calls: list[ToolCall] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        function = item.get("function") or {}
        name = function.get("name")
        if not name:
            continue
        calls.append(
            ToolCall(
                id=str(item.get("id") or name),
                name=str(name),
                arguments=function.get("arguments") or "{}",
            )
        )
    return calls
