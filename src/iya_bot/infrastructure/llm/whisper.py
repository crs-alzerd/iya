from __future__ import annotations

import logging

import httpx

from iya_bot.application.ports import SpeechTranscriber

logger = logging.getLogger(__name__)


class WhisperCompatibleTranscriber(SpeechTranscriber):
    """OpenAI-compatible /audio/transcriptions. Telegram отдаёт голос в OGG/Opus —
    его принимают и OpenAI Whisper, и большинство совместимых бэкендов."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "whisper-1",
        timeout_seconds: int = 60,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def transcribe(self, audio: bytes, *, filename: str = "voice.ogg", language: str | None = None) -> str:
        url = f"{self._base_url}/audio/transcriptions"
        data: dict[str, str] = {"model": self._model}
        if language:
            data["language"] = language
        files = {"file": (filename, audio, "audio/ogg")}
        try:
            response = await self._client.post(
                url,
                data=data,
                files=files,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:
            logger.exception("Voice transcription request failed")
            return ""
        text = payload.get("text") if isinstance(payload, dict) else None
        return text.strip() if isinstance(text, str) else ""
