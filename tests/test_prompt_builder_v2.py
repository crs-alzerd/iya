from iya_bot.application.prompt_builder import PromptBuilder
from iya_bot.domain.models import ChatMessage, MemoryItem, ModulationVector, RoutingDecision, SelfState


def test_prompt_builder_keeps_persona_anchor_and_memory() -> None:
    builder = PromptBuilder("BASE PROMPT", timezone_name="UTC", token_budget=4000, runtime_context_enabled=False)
    decision = RoutingDecision(
        profile="technical",
        vector=ModulationVector(technical_precision=0.9, structure=0.9),
        confidence=0.8,
        reason="test",
    )
    messages = builder.build(
        routing=decision,
        self_state=SelfState(telegram_user_id=1),
        relationship=None,
        memories=[],
        memory_facts=[
            MemoryItem(
                id=1,
                text="Пользователь разворачивает Ию на VPS.",
                author="user",
                source="manual",
                confidence=1.0,
                salience_score=1.0,
                status="active",
            )
        ],
        conversation_summary="Ия проектируется как manifest v2 assistant.",
        recent=[ChatMessage(role="user", content="как перезапустить контейнер?")],
    )
    joined = "\n".join(str(m.content) for m in messages)
    assert "Persona anchor v2" in joined
    assert "Пользователь разворачивает Ию на VPS" in joined
    assert "как перезапустить контейнер" in joined


def test_prompt_builder_drops_old_history_under_budget() -> None:
    builder = PromptBuilder("BASE", timezone_name="UTC", token_budget=800, runtime_context_enabled=False)
    decision = RoutingDecision(profile="default", vector=ModulationVector(), confidence=0.4, reason="test")
    recent = [ChatMessage(role="user", content="old " * 1000), ChatMessage(role="user", content="new")]
    messages = builder.build(
        routing=decision,
        self_state=None,
        relationship=None,
        memories=[],
        memory_facts=[],
        conversation_summary=None,
        recent=recent,
    )
    joined = "\n".join(str(m.content) for m in messages)
    assert "new" in joined
