from __future__ import annotations

import html
import logging
import re
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from iya_bot.application.ports import WebSearchClient
from iya_bot.domain.models import SearchResult

logger = logging.getLogger(__name__)

# Keyless HTML endpoint. Возвращает обычный HTML со списком результатов.
_DDG_HTML_URL = "https://html.duckduckgo.com/html/"
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_RESULT_LINK_RE = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_SNIPPET_RE = re.compile(
    r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(?P<snippet>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(value: str) -> str:
    return html.unescape(_TAG_RE.sub("", value)).strip()


def _normalize_href(href: str) -> str:
    # DuckDuckGo отдаёт ссылки-редиректы вида //duckduckgo.com/l/?uddg=<urlencoded>.
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg")
        if target:
            return unquote(target[0])
    return href


def parse_results(page_html: str, max_results: int = 5) -> list[SearchResult]:
    """Разобрать HTML выдачи DuckDuckGo в список результатов. Вынесено для юнит-тестов."""
    links = list(_RESULT_LINK_RE.finditer(page_html))
    snippets = _SNIPPET_RE.findall(page_html)
    results: list[SearchResult] = []
    for index, match in enumerate(links):
        title = _strip_html(match.group("title"))
        if not title:
            continue
        url = _normalize_href(match.group("href"))
        snippet = _strip_html(snippets[index]) if index < len(snippets) else ""
        results.append(SearchResult(title=title, url=url, snippet=snippet))
        if len(results) >= max_results:
            break
    return results


class DuckDuckGoSearchClient(WebSearchClient):
    def __init__(self, timeout_seconds: int = 15) -> None:
        self._timeout_seconds = timeout_seconds

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        headers = {"User-Agent": _USER_AGENT, "Accept-Language": "ru,en;q=0.9"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds, follow_redirects=True) as client:
                response = await client.post(_DDG_HTML_URL, data={"q": query}, headers=headers)
                response.raise_for_status()
                page_html = response.text
        except Exception:
            logger.exception("DuckDuckGo search failed for query=%r", query)
            return []
        return parse_results(page_html, max_results=max_results)
