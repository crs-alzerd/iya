from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolContext:
    """Контекст исполнения инструмента: за кого и в каком чате он вызван."""

    telegram_user_id: int


class Tool(ABC):
    """Один инструмент, который модель может вызвать через function-calling.

    name/description/parameters описывают инструмент для модели (OpenAI-формат),
    run() исполняет его и возвращает текст-результат, который уходит обратно модели.
    """

    name: str
    description: str
    parameters: dict

    @abstractmethod
    async def run(self, args: dict, ctx: ToolContext) -> str:
        raise NotImplementedError


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools: dict[str, Tool] = {tool.name: tool for tool in tools}

    def __bool__(self) -> bool:
        return bool(self._tools)

    def specs(self) -> list[dict]:
        """Список инструментов в формате OpenAI `tools`."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]

    async def run(self, name: str, arguments_json: str, ctx: ToolContext) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Инструмент '{name}' недоступен."
        try:
            args = json.loads(arguments_json) if arguments_json else {}
            if not isinstance(args, dict):
                args = {}
        except json.JSONDecodeError:
            return f"Не удалось разобрать аргументы инструмента '{name}'."
        try:
            return await tool.run(args, ctx)
        except Exception as exc:  # инструмент не должен ронять диалог
            logger.exception("Tool %s failed", name)
            return f"Инструмент '{name}' завершился ошибкой: {exc}"
