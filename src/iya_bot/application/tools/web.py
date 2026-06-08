from __future__ import annotations

from iya_bot.application.ports import PageFetcher, WebSearchClient
from iya_bot.application.tools.base import Tool, ToolContext


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Поиск в интернете для свежих, фактических или проверяемых сведений: новости, "
        "цены, версии, события, незнакомые имена и факты, всё что может устареть или чего "
        "нет в памяти модели. Возвращает список результатов с заголовком, ссылкой и сниппетом."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Поисковый запрос на естественном языке.",
            }
        },
        "required": ["query"],
    }

    def __init__(self, client: WebSearchClient, max_results: int = 5) -> None:
        self._client = client
        self._max_results = max_results

    async def run(self, args: dict, ctx: ToolContext) -> str:
        query = str(args.get("query") or "").strip()
        if not query:
            return "Пустой поисковый запрос."
        results = await self._client.search(query, max_results=self._max_results)
        if not results:
            return f"По запросу «{query}» ничего не нашлось."
        lines = [f"Результаты поиска по «{query}»:"]
        for index, result in enumerate(results, start=1):
            snippet = result.snippet.strip()
            lines.append(f"{index}. {result.title}\n{result.url}\n{snippet}")
        return "\n\n".join(lines)


class FetchUrlTool(Tool):
    name = "fetch_url"
    description = (
        "Открыть конкретную веб-страницу по URL и прочитать её текст. Используй после "
        "web_search, когда нужно достать детали со страницы, или когда пользователь дал ссылку."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Полный URL страницы (с http:// или https://).",
            }
        },
        "required": ["url"],
    }

    def __init__(self, fetcher: PageFetcher, max_chars: int = 4000) -> None:
        self._fetcher = fetcher
        self._max_chars = max_chars

    async def run(self, args: dict, ctx: ToolContext) -> str:
        url = str(args.get("url") or "").strip()
        if not url.lower().startswith(("http://", "https://")):
            return "Нужен корректный URL, начинающийся с http:// или https://."
        text = await self._fetcher.fetch(url)
        text = text.strip()
        if not text:
            return f"Страница {url} пустая или не отдала текст."
        if len(text) > self._max_chars:
            text = text[: self._max_chars].rstrip() + "…"
        return f"Содержимое {url}:\n{text}"
