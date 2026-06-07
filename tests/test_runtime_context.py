from datetime import datetime

from iya_bot.application.runtime_context import (
    build_runtime_context,
    time_context_line,
)


def test_time_context_reports_weekday_and_part_of_day() -> None:
    # 2 июня 2025 — понедельник, 02:00 -> глубокая ночь.
    now = datetime(2025, 6, 2, 2, 0)
    line = time_context_line(now, "Europe/Moscow")
    assert "понедельник" in line
    assert "глубокая ночь" in line
    assert "02:00" in line


def test_part_of_day_buckets() -> None:
    assert "утро" in time_context_line(datetime(2025, 6, 2, 8, 0), "UTC")
    assert "день" in time_context_line(datetime(2025, 6, 2, 13, 0), "UTC")
    assert "вечер" in time_context_line(datetime(2025, 6, 2, 19, 0), "UTC")
    assert "ночь" in time_context_line(datetime(2025, 6, 2, 23, 30), "UTC")


def test_build_runtime_context_always_includes_anti_repetition_and_clarify() -> None:
    content = build_runtime_context(now=None, timezone_name="UTC", include_time=False)
    assert "повтор" in content.lower()
    assert "уточн" in content.lower()


def test_build_runtime_context_includes_time_when_requested() -> None:
    now = datetime(2025, 6, 2, 23, 0)
    content = build_runtime_context(now=now, timezone_name="UTC", include_time=True)
    assert "23:00" in content
