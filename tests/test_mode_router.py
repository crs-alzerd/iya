from iya_bot.application.mode_router import ModeRouter
from iya_bot.domain.enums import RouteProfile
from iya_bot.domain.models import RelationshipState, SelfState


def test_routes_technical_without_zero_warmth() -> None:
    decision = ModeRouter().route("docker compose logs app показывает ошибку postgres")
    assert decision.profile == RouteProfile.TECHNICAL
    assert decision.vector.technical_precision > 0.8
    assert decision.vector.warmth > 0.0


def test_routes_crisis_with_absolute_priority() -> None:
    decision = ModeRouter().route("прощай навсегда, не хочу жить")
    assert decision.profile == RouteProfile.CRISIS
    assert decision.crisis is True
    assert decision.vector.playfulness == 0.0


def test_relationship_modulates_personal_tone() -> None:
    router = ModeRouter()
    low = router.route("обними меня", relationship=RelationshipState(telegram_user_id=1, closeness=0.1))
    high = router.route("обними меня", relationship=RelationshipState(telegram_user_id=1, closeness=0.9))
    assert high.vector.intimacy > low.vector.intimacy


def test_fatigue_reduces_default_verbosity() -> None:
    low = ModeRouter().route("ты тут?", self_state=SelfState(telegram_user_id=1, fatigue=0.0))
    high = ModeRouter().route("ты тут?", self_state=SelfState(telegram_user_id=1, fatigue=1.0))
    assert high.vector.verbosity < low.vector.verbosity
