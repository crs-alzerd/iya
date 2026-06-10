from __future__ import annotations

import time
from typing import AsyncIterator, Sequence

from iya_bot.application.ports import LLMClient, LLMRequestRepository
from iya_bot.domain.enums import LLMRequestStatus
from iya_bot.domain.models import ChatMessage, LLMRequestRecord, LLMResponse


class LLMRouter(LLMClient):
    """Thin manifest-v2 LLM router.

    This v1 keeps one provider/client but adds request-kind metadata and logging.
    Full multi-model routing can be added later without changing application services.
    """

    def __init__(
        self,
        client: LLMClient,
        *,
        provider: str,
        model: str,
        request_logs: LLMRequestRepository | None = None,
    ) -> None:
        self._client = client
        self._provider = provider
        self._model = model
        self._request_logs = request_logs

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        kind: str = "dialogue",
        telegram_user_id: int | None = None,
    ) -> str:
        started = time.perf_counter()
        try:
            response = await self._client.complete(messages, kind=kind, telegram_user_id=telegram_user_id)
        except Exception as exc:
            await self._record(
                telegram_user_id=telegram_user_id,
                kind=kind,
                status=LLMRequestStatus.FAILED,
                latency_ms=_elapsed_ms(started),
                error_text=str(exc)[:2000],
            )
            raise

        await self._record(
            telegram_user_id=telegram_user_id,
            kind=kind,
            status=LLMRequestStatus.SUCCESS,
            latency_ms=_elapsed_ms(started),
        )
        return response

    async def complete_tools(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: list[dict],
        kind: str = "dialogue",
        telegram_user_id: int | None = None,
    ) -> LLMResponse:
        started = time.perf_counter()
        try:
            response = await self._client.complete_tools(
                messages, tools=tools, kind=kind, telegram_user_id=telegram_user_id
            )
        except Exception as exc:
            await self._record(
                telegram_user_id=telegram_user_id,
                kind=kind,
                status=LLMRequestStatus.FAILED,
                latency_ms=_elapsed_ms(started),
                error_text=str(exc)[:2000],
            )
            raise

        await self._record(
            telegram_user_id=telegram_user_id,
            kind=kind,
            status=LLMRequestStatus.SUCCESS,
            latency_ms=_elapsed_ms(started),
        )
        return response

    async def complete_stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        kind: str = "dialogue",
        telegram_user_id: int | None = None,
    ) -> AsyncIterator[str]:
        started = time.perf_counter()
        try:
            async for delta in self._client.complete_stream(
                messages, kind=kind, telegram_user_id=telegram_user_id
            ):
                yield delta
        except Exception as exc:
            await self._record(
                telegram_user_id=telegram_user_id,
                kind=kind,
                status=LLMRequestStatus.FAILED,
                latency_ms=_elapsed_ms(started),
                error_text=str(exc)[:2000],
            )
            raise
        await self._record(
            telegram_user_id=telegram_user_id,
            kind=kind,
            status=LLMRequestStatus.SUCCESS,
            latency_ms=_elapsed_ms(started),
        )

    async def _record(
        self,
        *,
        telegram_user_id: int | None,
        kind: str,
        status: str,
        latency_ms: int,
        error_text: str | None = None,
    ) -> None:
        if self._request_logs is None:
            return
        try:
            await self._request_logs.add_request_record(
                LLMRequestRecord(
                    telegram_user_id=telegram_user_id,
                    kind=kind,
                    provider=self._provider,
                    model=self._model,
                    status=status,
                    latency_ms=latency_ms,
                    error_text=error_text,
                )
            )
        except Exception:
            # LLM logging must never break user-visible dialogue.
            return


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
