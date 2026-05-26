from datetime import UTC, datetime

import pytest

from iya_bot.application.reminders import ReminderParseError, parse_reminder_payload


def test_parse_minutes_reminder() -> None:
    due_at, text = parse_reminder_payload("10m проверить Ию")
    assert text == "проверить Ию"
    assert due_at.tzinfo is not None
    assert due_at > datetime.now(UTC)


def test_parse_invalid_reminder() -> None:
    with pytest.raises(ReminderParseError):
        parse_reminder_payload("потом что-нибудь")
