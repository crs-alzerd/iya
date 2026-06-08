from __future__ import annotations

from iya_bot.application.runtime_context import build_runtime_context, current_time_in
from iya_bot.domain.models import ChatMessage, MemoryItem, RelationshipState, RoutingDecision, SelfState


class PromptBuilder:
    """Manifest v2 prompt assembly with a simple token budget.

    The budget is approximate: we count characters / 4. This is not exact BPE,
    but it prevents uncontrolled context growth without adding a tokenizer dependency.
    """

    def __init__(
        self,
        system_prompt: str,
        *,
        timezone_name: str,
        token_budget: int = 12_000,
        runtime_context_enabled: bool = True,
    ) -> None:
        self._system_prompt = system_prompt.strip()
        self._timezone_name = timezone_name
        self._token_budget = max(2_000, token_budget)
        self._runtime_context_enabled = runtime_context_enabled

    def build(
        self,
        *,
        routing: RoutingDecision,
        self_state: SelfState | None,
        relationship: RelationshipState | None,
        memories: list[str],
        memory_facts: list[MemoryItem],
        conversation_summary: str | None,
        recent: list[ChatMessage],
    ) -> list[ChatMessage]:
        # Hard anchors: never drop.
        system_blocks = [self._persona_anchor(), self._system_prompt]
        if routing.crisis:
            system_blocks.append(_CRISIS_POLICY)

        system_blocks.append(self._modulation_block(routing))

        if self_state is not None:
            system_blocks.append(self._self_state_block(self_state))
        if relationship is not None:
            system_blocks.append(self._relationship_block(relationship))

        if self._runtime_context_enabled:
            now = current_time_in(self._timezone_name)
            system_blocks.append(
                build_runtime_context(now=now, timezone_name=self._timezone_name, include_time=now is not None)
            )

        optional_blocks: list[str] = []
        memory_block = self._memory_block(memory_facts=memory_facts, fallback_memories=memories)
        if memory_block:
            optional_blocks.append(memory_block)
        if conversation_summary:
            optional_blocks.append(
                "Краткая выжимка предыдущего диалога из базы данных. "
                "Учитывай её как долговременный контекст, но не пересказывай без нужды:\n"
                f"{conversation_summary.strip()}"
            )

        messages: list[ChatMessage] = [ChatMessage(role="system", content="\n\n".join(system_blocks))]
        messages.extend(ChatMessage(role="system", content=block) for block in self._fit_blocks(optional_blocks, messages))
        messages.extend(self._fit_recent_history(recent, messages))
        return messages

    def _persona_anchor(self) -> str:
        return (
            "Persona anchor v2: Ия — одна непрерывная личность, а не набор режимов. "
            "Она взрослая, спокойная, техно-интровертная, инженерно мыслящая и тёплая к пользователю. "
            "Технический ответ — это та же Ия, просто собранная и точная; личный ответ — та же Ия, просто мягче. "
            "Не выводи названия режимов, внутренние профили, численные параметры состояния или служебную маршрутизацию."
        )

    def _modulation_block(self, routing: RoutingDecision) -> str:
        v = routing.vector.clamp()
        return (
            "Модуляция ответа для текущего сообщения. Это внутренние настройки тона, не проговаривай их пользователю.\n"
            f"profile={routing.profile}; confidence={routing.confidence:.2f}; reason={routing.reason}\n"
            f"warmth={v.warmth:.2f}; verbosity={v.verbosity:.2f}; technical_precision={v.technical_precision:.2f}; "
            f"playfulness={v.playfulness:.2f}; intimacy={v.intimacy:.2f}; structure={v.structure:.2f}.\n"
            "Интерпретация: warmth не должен падать в ноль даже в техническом ответе; "
            "structure и technical_precision повышают проверяемость, но не превращают Ию в безличный справочник."
        )

    def _self_state_block(self, self_state: SelfState) -> str:
        return (
            "Self-state Ии. Это влияет на ритм и тон косвенно. Не объявляй эти значения пользователю.\n"
            + "\n".join(f"- {line}" for line in self_state.as_prompt_lines())
        )

    def _relationship_block(self, relationship: RelationshipState) -> str:
        return (
            "Relationship state. Используй только естественно, без отчёта пользователю.\n"
            f"- closeness={relationship.closeness:.2f}\n"
            f"- trust={relationship.trust:.2f}\n"
            f"- shared_history_len={relationship.shared_history_len}"
        )

    def _memory_block(self, *, memory_facts: list[MemoryItem], fallback_memories: list[str]) -> str | None:
        active_facts = [m for m in memory_facts if m.status == "active"]
        if active_facts:
            # Сортируем по важности, но в промпт отдаём только текст — без id,
            # source, confidence и salience. Это служебные поля, и манифест требует
            # не превращать память в отчёт. Ия должна вплетать факты естественно.
            ordered = sorted(active_facts, key=lambda m: (m.salience_score, m.confidence), reverse=True)[:20]
            lines = [f"- {m.text}" for m in ordered]
            return (
                "Что ты помнишь о пользователе и общих делах. "
                "Вплетай естественно, когда уместно, не зачитывай списком:\n" + "\n".join(lines)
            )
        if fallback_memories:
            return (
                "Что ты помнишь о пользователе и общих делах. "
                "Вплетай естественно, когда уместно, не зачитывай списком:\n"
                + "\n".join(f"- {m}" for m in fallback_memories)
            )
        return None

    def _fit_blocks(self, blocks: list[str], existing_messages: list[ChatMessage]) -> list[str]:
        result: list[str] = []
        for block in blocks:
            candidate = result + [block]
            if self._estimated_tokens(existing_messages, candidate) <= self._token_budget:
                result.append(block)
        return result

    def _fit_recent_history(self, recent: list[ChatMessage], existing_messages: list[ChatMessage]) -> list[ChatMessage]:
        # Drop oldest first. Current user message is already inside recent in current DialogueService.
        kept: list[ChatMessage] = []
        for message in reversed(recent):
            candidate = [message] + kept
            if self._estimated_tokens(existing_messages + candidate, []) <= self._token_budget:
                kept = candidate
            else:
                break
        return kept

    def _estimated_tokens(self, messages: list[ChatMessage], extra_blocks: list[str]) -> int:
        chars = 0
        for message in messages:
            content = message.content
            chars += len(str(content))
        chars += sum(len(block) for block in extra_blocks)
        return max(1, chars // 4)


_CRISIS_POLICY = (
    "Кризисный контур активен. Не уходи в RP, атмосферность или философию. "
    "Удерживай контакт, спроси один ли пользователь сейчас, предложи связаться с живым человеком "
    "или экстренной помощью, помоги дотянуть до ближайшего безопасного шага. Не используй чувство вины."
)
