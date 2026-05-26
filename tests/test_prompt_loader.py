from pathlib import Path

from iya_bot.application.prompt_loader import load_system_prompt


def test_load_system_prompt_from_external_file(tmp_path: Path) -> None:
    prompt = tmp_path / "iya_system.md"
    prompt.write_text("Внешний системный промпт", encoding="utf-8")

    assert load_system_prompt(str(prompt)) == "Внешний системный промпт"


def test_load_system_prompt_falls_back_to_bundled_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.md"

    content = load_system_prompt(str(missing))

    assert "Ты — Ия" in content
