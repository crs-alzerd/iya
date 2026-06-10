from __future__ import annotations

import asyncio
import html
import ipaddress
import logging
import re
from urllib.parse import urljoin, urlparse

import httpx

from iya_bot.application.ports import PageFetcher

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_MAX_REDIRECTS = 5

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


def is_blocked_ip(ip_text: str) -> bool:
    """SSRF-фильтр: запрещаем loopback, приватные сети, link-local (включая 169.254.169.254) и прочие служебные диапазоны."""
    try:
        addr = ipaddress.ip_address(ip_text)
    except ValueError:
        return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


async def _host_is_blocked(host: str) -> bool:
    """Хост запрещён, если это служебный IP или имя, которое резолвится в служебный IP."""
    try:
        return is_blocked_ip(str(ipaddress.ip_address(host)))
    except ValueError:
        pass
    try:
        loop = asyncio.get_running_loop()
        infos = await loop.getaddrinfo(host, None)
    except OSError:
        return True
    return any(is_blocked_ip(info[4][0]) for info in infos)


async def url_is_blocked(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return True
    return await _host_is_blocked(parsed.hostname)


class HttpPageFetcher(PageFetcher):
    def __init__(self, timeout_seconds: int = 15, max_bytes: int = 2_000_000) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes

    async def fetch(self, url: str) -> str:
        headers = {"User-Agent": _USER_AGENT, "Accept-Language": "ru,en;q=0.9"}
        current = url
        try:
            # Редиректы проходим вручную: каждый следующий адрес тоже проверяется
            # SSRF-фильтром, иначе публичный URL мог бы переадресовать во внутреннюю сеть.
            async with httpx.AsyncClient(timeout=self._timeout_seconds, follow_redirects=False) as client:
                for _ in range(_MAX_REDIRECTS + 1):
                    if await url_is_blocked(current):
                        logger.warning("Blocked fetch of internal/invalid url=%r", current)
                        return ""
                    response = await client.get(current, headers=headers)
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            return ""
                        current = urljoin(current, location)
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "")
                    raw = response.text[: self._max_bytes * 2]
                    break
                else:
                    logger.warning("Too many redirects for url=%r", url)
                    return ""
        except Exception:
            logger.exception("Failed to fetch url=%r", url)
            return ""
        if "html" not in content_type and "<" not in raw[:200]:
            # Похоже на не-HTML (json, текст) — отдаём как есть.
            return raw.strip()
        return html_to_text(raw)
