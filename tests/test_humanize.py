from iya_bot.application.humanize import (
    TELEGRAM_MAX_LEN,
    split_into_messages,
    typing_delay_seconds,
)


def test_short_text_stays_single_message() -> None:
    assert split_into_messages("я тут.", max_chunks=3) == ["я тут."]


def test_empty_text_returns_nothing() -> None:
    assert split_into_messages("   ", max_chunks=3) == []


def test_splits_paragraphs_into_separate_messages() -> None:
    text = "Первая мысль.\n\nВторая мысль.\n\nТретья мысль."
    chunks = split_into_messages(text, max_chunks=3)
    assert chunks == ["Первая мысль.", "Вторая мысль.", "Третья мысль."]


def test_merges_when_more_paragraphs_than_max_chunks() -> None:
    text = "А.\n\nБ.\n\nВ.\n\nГ.\n\nД."
    chunks = split_into_messages(text, max_chunks=2)
    assert len(chunks) == 2
    # Ничего не потеряли.
    joined = " ".join(chunks)
    for letter in ["А", "Б", "В", "Г", "Д"]:
        assert letter in joined


def test_max_chunks_one_keeps_everything_together() -> None:
    text = "Раз.\n\nДва.\n\nТри."
    chunks = split_into_messages(text, max_chunks=1)
    assert len(chunks) == 1
    assert "Раз." in chunks[0] and "Три." in chunks[0]


def test_never_exceeds_telegram_limit() -> None:
    long_text = "Предложение раз. " * 1000  # сильно длиннее 4096
    chunks = split_into_messages(long_text, max_chunks=3)
    assert all(len(c) <= TELEGRAM_MAX_LEN for c in chunks)


def test_typing_delay_is_clamped() -> None:
    assert typing_delay_seconds("x", min_seconds=0.6, max_seconds=4.0) == 0.6
    huge = "a" * 100000
    assert typing_delay_seconds(huge, min_seconds=0.6, max_seconds=4.0) == 4.0


def test_typing_delay_scales_between_bounds() -> None:
    medium = "a" * 100  # 100 * 22ms = 2.2s
    delay = typing_delay_seconds(medium, ms_per_char=22, min_seconds=0.6, max_seconds=4.0)
    assert 0.6 < delay < 4.0
