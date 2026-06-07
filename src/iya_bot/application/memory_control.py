from __future__ import annotations

from iya_bot.application.ports import MemoryRepository, RelationshipStateRepository, SelfStateRepository
from iya_bot.domain.models import MemoryItem, MemorySnapshot, RelationshipState, SelfState


class MemoryControlService:
    """Owner-facing memory diagnostics and safety operations."""

    def __init__(
        self,
        memories: MemoryRepository,
        self_states: SelfStateRepository | None = None,
        relationships: RelationshipStateRepository | None = None,
    ) -> None:
        self._memories = memories
        self._self_states = self_states
        self._relationships = relationships

    async def list_memory(self, telegram_user_id: int) -> list[MemoryItem]:
        return await self._memories.list_memory_items(telegram_user_id, include_archived=False)

    async def get_summary(self, telegram_user_id: int) -> str | None:
        return await self._memories.get_conversation_summary(telegram_user_id)

    async def forget(self, telegram_user_id: int, memory_id: int) -> bool:
        return await self._memories.archive_memory(telegram_user_id, memory_id)

    async def create_snapshot(self, telegram_user_id: int, reason: str) -> int:
        return await self._memories.create_memory_snapshot(telegram_user_id, reason)

    async def list_snapshots(self, telegram_user_id: int) -> list[MemorySnapshot]:
        return await self._memories.list_memory_snapshots(telegram_user_id)

    async def get_self_state(self, telegram_user_id: int) -> SelfState | None:
        if self._self_states is None:
            return None
        return await self._self_states.get_or_create_state(telegram_user_id)

    async def get_relationship(self, telegram_user_id: int) -> RelationshipState | None:
        if self._relationships is None:
            return None
        return await self._relationships.get_or_create_relationship(telegram_user_id)


def format_memory_items(items: list[MemoryItem]) -> str:
    if not items:
        return "Активная память пока пустая."
    lines = ["Активная память:"]
    for item in items:
        lines.append(
            f"#{item.id} [{item.source}; conf={item.confidence:.2f}; salience={item.salience_score:.2f}] {item.text}"
        )
    return "\n".join(lines)


def format_self_diagnostics(state: SelfState | None, relationship: RelationshipState | None) -> str:
    blocks: list[str] = []
    if state is None:
        blocks.append("self_state: disabled")
    else:
        blocks.append(
            "self_state:\n"
            f"- composure={state.composure:.2f}\n"
            f"- warmth_now={state.warmth_now:.2f}\n"
            f"- engagement={state.engagement:.2f}\n"
            f"- fatigue={state.fatigue:.2f}\n"
            f"- playfulness={state.playfulness:.2f}"
        )
    if relationship is None:
        blocks.append("relationship_state: disabled")
    else:
        blocks.append(
            "relationship_state:\n"
            f"- closeness={relationship.closeness:.2f}\n"
            f"- trust={relationship.trust:.2f}\n"
            f"- shared_history_len={relationship.shared_history_len}"
        )
    return "\n\n".join(blocks)
