import iya_bot.infrastructure.llm.openai_compatible as mod
from iya_bot.domain.models import ChatMessage
from iya_bot.infrastructure.llm.openai_compatible import (
    LLMSamplingParams,
    OpenAICompatibleClient,
)


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    captured: dict = {}

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def post(self, url: str, json: dict, headers: dict) -> _FakeResponse:
        _FakeAsyncClient.captured = json
        return _FakeResponse(
            {"choices": [{"message": {"content": "ok"}}]}
        )


async def test_penalties_are_included_when_set(monkeypatch) -> None:
    monkeypatch.setattr(mod.httpx, "AsyncClient", _FakeAsyncClient)
    client = OpenAICompatibleClient(
        base_url="https://x/v1",
        api_key="k",
        model="m",
        sampling=LLMSamplingParams(
            temperature=0.9,
            presence_penalty=0.4,
            frequency_penalty=0.5,
        ),
    )
    result = await client.complete([ChatMessage(role="user", content="hi")])
    assert result == "ok"
    payload = _FakeAsyncClient.captured
    assert payload["temperature"] == 0.9
    assert payload["presence_penalty"] == 0.4
    assert payload["frequency_penalty"] == 0.5
    # top_p / max_tokens не заданы -> не должны попасть в payload.
    assert "top_p" not in payload
    assert "max_tokens" not in payload


async def test_optional_params_omitted_when_none(monkeypatch) -> None:
    monkeypatch.setattr(mod.httpx, "AsyncClient", _FakeAsyncClient)
    client = OpenAICompatibleClient(
        base_url="https://x/v1",
        api_key="k",
        model="m",
        sampling=LLMSamplingParams(
            temperature=0.7,
            presence_penalty=None,
            frequency_penalty=None,
        ),
    )
    await client.complete([ChatMessage(role="user", content="hi")])
    payload = _FakeAsyncClient.captured
    assert "presence_penalty" not in payload
    assert "frequency_penalty" not in payload
