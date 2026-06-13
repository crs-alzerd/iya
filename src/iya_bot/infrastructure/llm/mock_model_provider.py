from __future__ import annotations

from iya_bot.application.ports import ModelProvider


class CannedModelProvider(ModelProvider):
    """Mock-LLM для planning-подсистемы: детерминированные ответы без сети.

    Замена реального адаптера поверх LLMRouter/nanogpt на время сборки
    фундамента. Можно задать фиксированные ответы либо callable от промпта,
    чтобы тесты бизнес-логики не зависели от настоящей модели.
    """

    def __init__(self, responses: list[str] | None = None, *, default: str = "") -> None:
        self._responses = list(responses or [])
        self._default = default
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self._responses:
            return self._responses.pop(0)
        return self._default
