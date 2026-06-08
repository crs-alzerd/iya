from __future__ import annotations

import html
import logging
import re

import httpx

from iya_bot.application.ports import PageFetcher

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Вырезаем скрипты/стили целиком, затем все теги, затем схлопываем пробелы.
_DROP_BLOCK_RE = re.compile(r"<(script|style|noscript|template)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")


def html_to_text(page_html: str) -> str:
    text = _DROP_BLOCK_RE.sub(" ", page_html)
    text = _TAG_RE.sub("\n", text)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text)
    text = _MULTI_NL_RE.sub("\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


class HttpPageFetcher(PageFetcher):
    def __init__(self, timeout_seconds: int = 15, max_bytes: int = 2_000_000) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes

    async def fetch(self, url: str) -> str:
        headers = {"User-Agent": _USER_AGENT, "Accept-Language": "ru,en;q=0.9"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                raw = response.text[: self._max_bytes * 2]
        except Exception:
            logger.exception("Failed to fetch url=%r", url)
            return ""
        if "html" not in content_type and "<" not in raw[:200]:
            # Похоже на не-HTML (json, текст) — отдаём как есть.
            return raw.strip()
        return html_to_text(raw)
