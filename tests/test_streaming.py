from pathlib import Path

from iya_bot.application.dialogue import DialogueService
from iya_bot.infrastructure.llm.openai_compatible import extract_stream_delta
from test_dialogue import FakeMemoryRepository, FakeMessageRepository, FakeUserRepository


def test_extract_stream_delta_parses_content() -> None:
    line = 'data: {"choices":[{"delta":{"content":"при"}}]}'
    assert extract_stream_delta(line) == "при"


def test_extract_stream_delta_ignores_noise() -> None:
    assert extract_stream_delta("") is None
    assert extract_stream_delta(": keep-alive") is None
    assert extract_stream_delta("data: [DONE]") is None
    assert extract_stream_delta("data: {not json") is None
    assert extract_stream_delta('data: {"choices":[]}') is None
    assert extract_stream_delta('data: {"choices":[{"delta":{}}]}') is None
    assert extract_stream_delta('data: {"choices":[{"delta":{"content":""}}]}') is None


class StreamingFakeLLM:
    """LLM с поддержкой complete_stream; complete используется для фоновой выжимки."""

    def __init__(self, deltas: list[str]) -> None:
        self._deltas = deltas
        self.stream_calls = 0

    async def complete_stream(self, messages, *, kind="dialogue", telegram_user_id=None):
        self.stream_calls += 1
        for delta in self._deltas:
            yield delta

    async def complete(self, messages, *, kind="dialogue", telegram_user_id=None) -> str:
        return "Выжимка"


class EmptyStreamFakeLLM(StreamingFakeLLM):
    def __init__(self) -> None:
        super().__init__([])

    async def complete(self, messages, *, kind="dialogue", telegram_user_id=None) -> str:
        return "Запасной ответ"


async def test_answer_streams_progress_and_returns_full_text(tmp_path: Path) -> None:
    prompt = tmp_path / "system.md"
    prompt.write_text("Системный промпт", encoding="utf-8")
    llm = StreamingFakeLLM(["При", "вет", "!"])
    dialogue = DialogueService(
        users=FakeUserRepository(),
        messages=FakeMessageRepository(),
        memories=FakeMemoryRepository(memories=[], summary=None),
        llm=llm,
        history_limit=20,
        system_prompt_path=str(prompt),
    )
    snapshots: list[str] = []

    async def progress(text: str) -> None:
        snapshots.append(text)

    result = await dialogue.answer(
        telegram_user_id=7, username=None, first_name=None, last_name=None, text="привет", progress=progress
    )
    await dialogue.drain_background_tasks()

    assert result.text == "Привет!"
    assert snapshots == ["При", "Привет", "Привет!"]
    assert llm.stream_calls == 1


async def test_empty_stream_falls_back_to_complete(tmp_path: Path) -> None:
    prompt = tmp_path / "system.md"
    prompt.write_text("Системный промпт", encoding="utf-8")
    dialogue = DialogueService(
        users=FakeUserRepository(),
        messages=FakeMessageRepository(),
        memories=FakeMemoryRepository(memories=[], summary=None),
        llm=EmptyStreamFakeLLM(),
        history_limit=20,
        system_prompt_path=str(prompt),
    )

    async def progress(text: str) -> None:
        pass

    result = await dialogue.answer(
        telegram_user_id=7, username=None, first_name=None, last_name=None, text="привет", progress=progress
    )
    await dialogue.drain_background_tasks()
    assert result.text == "Запасной ответ"


async def test_progress_callback_errors_do_not_break_answer(tmp_path: Path) -> None:
    prompt = tmp_path / "system.md"
    prompt.write_text("Системный промпт", encoding="utf-8")
    dialogue = DialogueService(
        users=FakeUserRepository(),
        messages=FakeMessageRepository(),
        memories=FakeMemoryRepository(memories=[], summary=None),
        llm=StreamingFakeLLM(["Ответ"]),
        history_limit=20,
        system_prompt_path=str(prompt),
    )

    async def broken_progress(text: str) -> None:
        raise RuntimeError("edit failed")

    result = await dialogue.answer(
        telegram_user_id=7, username=None, first_name=None, last_name=None, text="привет", progress=broken_progress
    )
    await dialogue.drain_background_tasks()
    assert result.text == "Ответ"
