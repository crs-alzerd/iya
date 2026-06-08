import pytest

from iya_bot.application.tools.base import Tool, ToolContext, ToolRegistry
from iya_bot.application.tools.memory import RememberFactTool
from iya_bot.application.tools.web import FetchUrlTool, WebSearchTool
from iya_bot.domain.models import SearchResult


class FakeSearchClient:
    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results
        self.queries: list[str] = []

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        self.queries.append(query)
        return self.results[:max_results]


class FakeFetcher:
    def __init__(self, text: str) -> None:
        self.text = text
        self.urls: list[str] = []

    async def fetch(self, url: str) -> str:
        self.urls.append(url)
        return self.text


class FakeMemoryRepo:
    def __init__(self) -> None:
        self.saved: list[tuple[int, str]] = []

    async def add_memory(self, telegram_user_id: int, content: str) -> None:
        self.saved.append((telegram_user_id, content))


CTX = ToolContext(telegram_user_id=42)


async def test_registry_specs_use_openai_format():
    tool = RememberFactTool(FakeMemoryRepo())
    registry = ToolRegistry([tool])
    specs = registry.specs()
    assert specs[0]["type"] == "function"
    assert specs[0]["function"]["name"] == "remember_fact"
    assert "parameters" in specs[0]["function"]
    assert bool(registry) is True


async def test_registry_unknown_tool_is_graceful():
    registry = ToolRegistry([])
    assert bool(registry) is False
    result = await registry.run("nope", "{}", CTX)
    assert "недоступен" in result


async def test_registry_bad_arguments_are_graceful():
    registry = ToolRegistry([RememberFactTool(FakeMemoryRepo())])
    result = await registry.run("remember_fact", "{not json", CTX)
    assert "разобрать" in result.lower()


async def test_web_search_tool_formats_results():
    client = FakeSearchClient(
        [
            SearchResult(title="Title A", url="https://a.test", snippet="Snippet A"),
            SearchResult(title="Title B", url="https://b.test", snippet="Snippet B"),
        ]
    )
    tool = WebSearchTool(client, max_results=5)
    out = await tool.run({"query": "погода"}, CTX)
    assert client.queries == ["погода"]
    assert "Title A" in out and "https://a.test" in out and "Snippet A" in out
    assert "Title B" in out


async def test_web_search_tool_handles_empty():
    tool = WebSearchTool(FakeSearchClient([]), max_results=5)
    out = await tool.run({"query": "ничего"}, CTX)
    assert "ничего не нашлось" in out


async def test_fetch_url_tool_truncates():
    tool = FetchUrlTool(FakeFetcher("x" * 100), max_chars=10)
    out = await tool.run({"url": "https://example.com"}, CTX)
    assert out.startswith("Содержимое https://example.com")
    assert "…" in out


async def test_fetch_url_tool_rejects_bad_url():
    tool = FetchUrlTool(FakeFetcher("data"), max_chars=10)
    out = await tool.run({"url": "ftp://x"}, CTX)
    assert "http://" in out


async def test_remember_fact_tool_saves():
    repo = FakeMemoryRepo()
    tool = RememberFactTool(repo)
    out = await tool.run({"fact": "Любит зиму"}, CTX)
    assert repo.saved == [(42, "Любит зиму")]
    assert "Запомнила" in out


async def test_remember_fact_tool_rejects_empty():
    repo = FakeMemoryRepo()
    tool = RememberFactTool(repo)
    out = await tool.run({"fact": "  "}, CTX)
    assert repo.saved == []
    assert "пуст" in out.lower()


async def test_tool_run_catches_exceptions():
    class BoomTool(Tool):
        name = "boom"
        description = "x"
        parameters = {"type": "object", "properties": {}}

        async def run(self, args, ctx):
            raise RuntimeError("kaboom")

    registry = ToolRegistry([BoomTool()])
    out = await registry.run("boom", "{}", CTX)
    assert "ошибк" in out.lower()
