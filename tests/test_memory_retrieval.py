from iya_bot.application.memory_retrieval import (
    MemoryRetrievalService,
    cosine_similarity,
    rank_by_relevance,
)
from iya_bot.domain.models import MemoryItem


def _item(id: int, text: str, *, salience: float = 0.5, embedding: list[float] | None = None) -> MemoryItem:
    return MemoryItem(
        id=id,
        text=text,
        author="extracted",
        source="extracted",
        confidence=0.7,
        salience_score=salience,
        status="active",
        embedding=embedding,
    )


def test_cosine_similarity_basic() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0


def test_cosine_similarity_degenerate_inputs() -> None:
    assert cosine_similarity([], [1.0]) == 0.0
    assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_rank_prefers_semantically_close_facts() -> None:
    query = [1.0, 0.0]
    relevant = _item(1, "близкий факт", salience=0.1, embedding=[0.99, 0.05])
    irrelevant = _item(2, "далёкий факт", salience=0.9, embedding=[0.0, 1.0])

    ranked = rank_by_relevance(query, [irrelevant, relevant], top_k=1)
    assert [item.id for item in ranked] == [1]


def test_rank_fills_tail_with_unembedded_by_salience() -> None:
    query = [1.0, 0.0]
    embedded = _item(1, "с эмбеддингом", embedding=[1.0, 0.0])
    missing_hi = _item(2, "без эмбеддинга, важный", salience=0.9)
    missing_lo = _item(3, "без эмбеддинга, неважный", salience=0.1)

    ranked = rank_by_relevance(query, [missing_lo, missing_hi, embedded], top_k=2)
    assert [item.id for item in ranked] == [1, 2]


class FakeEmbedder:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [self.vectors[text] for text in texts]


class BrokenEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embeddings down")


class FakeMemories:
    def __init__(self, missing: list[MemoryItem]) -> None:
        self.missing = missing
        self.stored: list[tuple[int, list[float]]] = []

    async def list_facts_missing_embedding(self, telegram_user_id: int, limit: int = 20) -> list[MemoryItem]:
        return self.missing[:limit]

    async def set_fact_embedding(self, telegram_user_id: int, memory_id: int, embedding: list[float]) -> None:
        self.stored.append((memory_id, embedding))


async def test_select_relevant_skips_embedding_when_few_items() -> None:
    embedder = FakeEmbedder({})
    service = MemoryRetrievalService(embedder, FakeMemories([]), top_k=20)
    items = [_item(1, "x")]

    assert await service.select_relevant("вопрос", items) == items
    assert embedder.calls == []


async def test_select_relevant_ranks_by_query_embedding() -> None:
    embedder = FakeEmbedder({"зима": [1.0, 0.0]})
    service = MemoryRetrievalService(embedder, FakeMemories([]), top_k=1)
    relevant = _item(1, "любит зиму", embedding=[1.0, 0.0])
    other = _item(2, "пьёт кофе", embedding=[0.0, 1.0])

    result = await service.select_relevant("зима", [other, relevant])
    assert [item.id for item in result] == [1]


async def test_select_relevant_falls_back_on_embedding_failure() -> None:
    service = MemoryRetrievalService(BrokenEmbedder(), FakeMemories([]), top_k=1)
    items = [_item(1, "a", salience=0.9), _item(2, "b", salience=0.1)]

    result = await service.select_relevant("вопрос", items)
    assert [item.id for item in result] == [1]


async def test_backfill_embeds_missing_facts() -> None:
    missing = [_item(1, "факт один"), _item(2, "факт два")]
    memories = FakeMemories(missing)
    embedder = FakeEmbedder({"факт один": [0.1], "факт два": [0.2]})
    service = MemoryRetrievalService(embedder, memories, top_k=20)

    updated = await service.backfill(42)
    assert updated == 2
    assert memories.stored == [(1, [0.1]), (2, [0.2])]


async def test_backfill_survives_embedder_failure() -> None:
    memories = FakeMemories([_item(1, "факт")])
    service = MemoryRetrievalService(BrokenEmbedder(), memories, top_k=20)

    assert await service.backfill(42) == 0
    assert memories.stored == []


class RecordingRetrieval:
    """Подменный retrieval для проверки интеграции с DialogueService."""

    def __init__(self) -> None:
        self.select_queries: list[str] = []
        self.backfilled: list[int] = []

    async def select_relevant(self, query: str, items: list[MemoryItem]) -> list[MemoryItem]:
        self.select_queries.append(query)
        return items[:1]

    async def backfill(self, telegram_user_id: int) -> int:
        self.backfilled.append(telegram_user_id)
        return 0


async def test_dialogue_uses_retrieval_and_backfills(tmp_path) -> None:
    from iya_bot.application.dialogue import DialogueService
    from test_dialogue import FakeLLMClient, FakeMessageRepository, FakeUserRepository

    class FactsMemoryRepo:
        def __init__(self) -> None:
            self.summary = None

        async def list_memory_items(self, telegram_user_id, include_archived=False, limit=50):
            return [_item(1, "факт раз"), _item(2, "факт два")]

        async def get_memories(self, telegram_user_id, limit=20):
            return []

        async def get_conversation_summary(self, telegram_user_id):
            return None

        async def upsert_conversation_summary(self, telegram_user_id, content):
            self.summary = content

    prompt = tmp_path / "system.md"
    prompt.write_text("Системный промпт", encoding="utf-8")
    retrieval = RecordingRetrieval()
    dialogue = DialogueService(
        users=FakeUserRepository(),
        messages=FakeMessageRepository(),
        memories=FactsMemoryRepo(),
        llm=FakeLLMClient(["Ответ", "Выжимка"]),
        history_limit=20,
        system_prompt_path=str(prompt),
        memory_retrieval=retrieval,
    )

    await dialogue.answer(telegram_user_id=42, username=None, first_name=None, last_name=None, text="зима")
    await dialogue.drain_background_tasks()

    assert retrieval.select_queries == ["зима"]
    assert retrieval.backfilled == [42]
