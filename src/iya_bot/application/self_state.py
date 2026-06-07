from __future__ import annotations

from datetime import datetime

from iya_bot.application.ports import RelationshipStateRepository, SelfStateRepository
from iya_bot.domain.enums import RouteProfile
from iya_bot.domain.models import RelationshipState, RoutingDecision, SelfState


class SelfStateService:
    """Deterministic self-state v1.

    LLM не пишет состояние напрямую. Код плавно обновляет значения по правилам,
    чтобы не получить театральный или нестабильный дрейф личности.
    """

    def __init__(
        self,
        states: SelfStateRepository,
        relationships: RelationshipStateRepository | None = None,
    ) -> None:
        self._states = states
        self._relationships = relationships

    async def get_state(self, telegram_user_id: int) -> SelfState:
        return await self._states.get_or_create_state(telegram_user_id)

    async def get_relationship(self, telegram_user_id: int) -> RelationshipState | None:
        if self._relationships is None:
            return None
        return await self._relationships.get_or_create_relationship(telegram_user_id)

    async def update_after_turn(
        self,
        telegram_user_id: int,
        routing: RoutingDecision,
        *,
        now: datetime | None = None,
    ) -> None:
        current = await self._states.get_or_create_state(telegram_user_id)
        hour = (now or datetime.now()).hour
        night_fatigue_delta = 0.03 if hour >= 23 or hour < 5 else -0.02

        engagement_delta = 0.0
        warmth_delta = 0.0
        playfulness_delta = -0.01
        composure_delta = 0.01

        if routing.profile == RouteProfile.TECHNICAL:
            engagement_delta = 0.06
            warmth_delta = -0.01
            playfulness_delta = -0.02
        elif routing.profile in {RouteProfile.PERSONAL, RouteProfile.RP, RouteProfile.SUPPORT}:
            warmth_delta = 0.04
            engagement_delta = 0.03
            playfulness_delta = 0.01 if routing.profile == RouteProfile.RP else 0.0
        elif routing.profile == RouteProfile.CRISIS:
            composure_delta = 0.08
            warmth_delta = 0.05
            engagement_delta = 0.08
            playfulness_delta = -0.08

        updated = SelfState(
            telegram_user_id=telegram_user_id,
            composure=_clamp(current.composure + composure_delta, 0.2, 1.0),
            warmth_now=_clamp(current.warmth_now + warmth_delta, 0.2, 1.0),
            engagement=_clamp(current.engagement + engagement_delta, 0.1, 1.0),
            fatigue=_clamp(current.fatigue + night_fatigue_delta, 0.0, 1.0),
            playfulness=_clamp(current.playfulness + playfulness_delta, 0.0, 0.8),
        )
        await self._states.upsert_state(updated)

        if self._relationships is not None:
            relation = await self._relationships.get_or_create_relationship(telegram_user_id)
            await self._relationships.upsert_relationship(
                RelationshipState(
                    telegram_user_id=telegram_user_id,
                    closeness=_clamp(relation.closeness + 0.002, 0.0, 1.0),
                    trust=_clamp(relation.trust + (0.003 if routing.profile == RouteProfile.TECHNICAL else 0.001), 0.0, 1.0),
                    shared_history_len=relation.shared_history_len + 1,
                    inside_refs=relation.inside_refs,
                )
            )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
