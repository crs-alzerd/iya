import logging
from importlib.resources import files
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PACKAGE_PROMPT = "iya_system.md"


class SystemPromptError(RuntimeError):
    pass


def load_system_prompt(system_prompt_path: str | None = None) -> str:
    """Load Iya system prompt from an external file with package fallback.

    The external path is intended for VPS operation: edit prompts/iya_system.md,
    then restart the app container. If the file is missing, the bundled prompt
    remains a safe fallback so the bot can still start.
    """
    candidates: list[tuple[str, Path | None]] = []

    if system_prompt_path:
        candidates.append(("external", Path(system_prompt_path).expanduser()))

    for source, path in candidates:
        if path is None:
            continue
        if not path.exists():
            logger.warning("System prompt %s path does not exist: %s", source, path)
            continue
        if not path.is_file():
            logger.warning("System prompt %s path is not a file: %s", source, path)
            continue
        content = path.read_text(encoding="utf-8").strip()
        if content:
            logger.info("Loaded system prompt from %s path: %s", source, path)
            return content
        logger.warning("System prompt %s path is empty: %s", source, path)

    bundled = files("iya_bot.prompts").joinpath(DEFAULT_PACKAGE_PROMPT)
    content = bundled.read_text(encoding="utf-8").strip()
    if not content:
        raise SystemPromptError("Bundled system prompt is empty.")

    logger.info("Loaded bundled system prompt fallback: %s", DEFAULT_PACKAGE_PROMPT)
    return content
