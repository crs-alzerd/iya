from __future__ import annotations

from iya_bot.application.ports import MemoryRepository
from iya_bot.application.tools.base import Tool, ToolContext


class RememberFactTool(Tool):
    name = "remember_fact"
    description = (
        "Сохранить в долговременную память один устойчивый факт о пользователе или общих делах "
        "(предпочтения, важные обстоятельства, решения, договорённости). Используй, когда хочешь "
        "осознанно запомнить что-то важное на будущее. Не сохраняй мелочи и сиюминутный шум."
    )
    parameters = {
        "type": "object",
        "properties": {
            "fact": {
                "type": "string",
                "description": "Короткая самодостаточная формулировка факта.",
            }
        },
        "required": ["fact"],
    }

    def __init__(self, memories: MemoryRepository) -> None:
        self._memories = memories

    async def run(self, args: dict, ctx: ToolContext) -> str:
        fact = str(args.get("fact") or "").strip()
        if not fact:
            return "Нечего запоминать: факт пустой."
        await self._memories.add_memory(ctx.telegram_user_id, fact)
        return f"Запомнила: {fact}"
