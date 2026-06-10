import iya_bot.infrastructure.telegram.handlers as handlers_mod
from iya_bot.domain.models import DialogueResult
from iya_bot.infrastructure.telegram.handlers import StreamingEditor, _clip_for_telegram, _send_humanized
from test_config import _settings


class FakeSentMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.edits: list[str] = []

    async def edit_text(self, text: str) -> None:
        self.edits.append(text)
        self.text = text


class FakeBot:
    def __init__(self) -> None:
        self.chat_actions = 0

    async def send_chat_action(self, chat_id: int, action: str) -> None:
        self.chat_actions += 1


class FakeMessage:
    def __init__(self) -> None:
        self.bot = FakeBot()
        self.chat = type("Chat", (), {"id": 1})()
        self.sent: list[FakeSentMessage] = []

    async def answer(self, text: str) -> FakeSentMessage:
        message = FakeSentMessage(text)
        self.sent.append(message)
        return message


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


async def test_streaming_editor_sends_then_edits_with_throttle(monkeypatch) -> None:
    clock = FakeClock()
    monkeypatch.setattr(handlers_mod.time, "monotonic", clock)
    message = FakeMessage()
    editor = StreamingEditor(message, edit_interval_seconds=1.5)

    await editor.update("При")
    assert editor.started
    assert message.sent[0].text == "При" + StreamingEditor.CURSOR

    # Слишком рано — правка пропускается.
    await editor.update("Привет")
    assert message.sent[0].edits == []

    clock.now += 2.0
    await editor.update("Привет, как")
    assert message.sent[0].edits == ["Привет, как" + StreamingEditor.CURSOR]

    await editor.finalize("Привет, как дела?")
    assert message.sent[0].text == "Привет, как дела?"


async def test_streaming_editor_ignores_empty_updates_and_noop_finalize() -> None:
    message = FakeMessage()
    editor = StreamingEditor(message, edit_interval_seconds=1.5)

    await editor.update("   ")
    assert not editor.started
    await editor.finalize("текст")  # ничего не отправляли — finalize тихо выходит
    assert message.sent == []


def test_clip_for_telegram() -> None:
    assert _clip_for_telegram("abc") == "abc"
    clipped = _clip_for_telegram("x" * 5000)
    assert len(clipped) == 4096
    assert clipped.endswith("…")


async def test_send_humanized_respects_single_message_profile() -> None:
    message = FakeMessage()
    settings = _settings(HUMANIZE_ENABLED="true", HUMANIZE_MAX_CHUNKS="3")
    answer = DialogueResult(text="Первый абзац.\n\nВторой абзац.", max_messages=1)

    await _send_humanized(message, answer, settings)
    assert len(message.sent) == 1
    assert "Первый абзац." in message.sent[0].text


async def test_send_humanized_chunks_default_profile() -> None:
    message = FakeMessage()
    settings = _settings(
        HUMANIZE_ENABLED="true",
        HUMANIZE_MAX_CHUNKS="3",
        HUMANIZE_MIN_DELAY_SECONDS="0",
        HUMANIZE_MAX_DELAY_SECONDS="0",
    )
    answer = DialogueResult(text="Первый абзац.\n\nВторой абзац.", max_messages=2)

    await _send_humanized(message, answer, settings)
    assert len(message.sent) == 2
    # Перед вторым куском показывался typing-индикатор.
    assert message.bot.chat_actions == 1


async def test_send_humanized_single_message_when_disabled() -> None:
    message = FakeMessage()
    settings = _settings(HUMANIZE_ENABLED="false")
    answer = DialogueResult(text="Первый.\n\nВторой.", max_messages=2)

    await _send_humanized(message, answer, settings)
    assert len(message.sent) == 1
