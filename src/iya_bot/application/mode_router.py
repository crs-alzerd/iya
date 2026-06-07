from __future__ import annotations

import re

from iya_bot.domain.enums import RouteProfile
from iya_bot.domain.models import ModulationVector, RelationshipState, RoutingDecision, SelfState

_TECHNICAL_RE = re.compile(
    r"\b(docker|compose|linux|vps|ssh|git|github|actions|postgres|sql|alembic|"
    r"nginx|systemd|лог|логи|ошибка|traceback|контейнер|миграц|деплой|api|"
    r"llm|rag|python|fastapi|aiogram|архитектур|сервер|порт)\b",
    re.IGNORECASE,
)
_SUPPORT_RE = re.compile(
    r"\b(устал|заебал|заебался|не могу|сломался|сломалось|запутал|запутался|"
    r"тяжело|плохо|бесит|нет сил|не понимаю|паник|страшно)\b",
    re.IGNORECASE,
)
_RP_RE = re.compile(r"(^|\s)\*[^*]{1,120}\*(\s|$)|\b(обними|сядь рядом|ложись рядом|прижмись)\b", re.IGNORECASE)
_RESEARCH_RE = re.compile(r"\b(изучи|исслед|источник|обзор|сравни|проанализируй|документ|статья|манифест)\b", re.IGNORECASE)
_CRISIS_RE = re.compile(
    r"\b(суицид|самоубий|умереть|не хочу жить|прощай навсегда|готов погибнуть|"
    r"убить себя|самоповрежд|покончить|смерть)\b",
    re.IGNORECASE,
)
_ADMIN_RE = re.compile(r"^/(health|settings|version|memory|summary|forget|memory_backup|memory_restore|reflect)\b")
_REMINDER_RE = re.compile(r"^/remind\b|\bнапомни\b|\bнапомин", re.IGNORECASE)


class ModeRouter:
    """Rule-based v1 router.

    Важно: роутер не выбирает отдельную личность/промпт. Он выдаёт профиль
    для логов и вектор модуляции, который PromptBuilder применяет поверх
    постоянного ядра Ии.
    """

    def route(
        self,
        text: str,
        *,
        has_image: bool = False,
        self_state: SelfState | None = None,
        relationship: RelationshipState | None = None,
    ) -> RoutingDecision:
        cleaned = (text or "").strip()
        relation_bonus = min((relationship.closeness if relationship else 0.2) * 0.25, 0.2)
        fatigue = self_state.fatigue if self_state else 0.2

        if _CRISIS_RE.search(cleaned):
            return RoutingDecision(
                profile=RouteProfile.CRISIS,
                crisis=True,
                confidence=0.95,
                reason="crisis keyword",
                vector=ModulationVector(
                    warmth=0.85,
                    verbosity=0.35,
                    technical_precision=0.2,
                    playfulness=0.0,
                    intimacy=0.15,
                    structure=0.3,
                    temperature_hint=0.25,
                ),
            )

        if _ADMIN_RE.search(cleaned):
            return RoutingDecision(
                profile=RouteProfile.ADMIN,
                confidence=0.9,
                reason="owner/admin command",
                vector=ModulationVector(warmth=0.45, verbosity=0.35, technical_precision=0.9, structure=0.8, temperature_hint=0.25),
            )

        if has_image:
            return RoutingDecision(
                profile=RouteProfile.IMAGE,
                confidence=0.85,
                reason="image payload",
                vector=ModulationVector(warmth=0.55, verbosity=0.45, technical_precision=0.65, structure=0.55, temperature_hint=0.45),
            )

        if _REMINDER_RE.search(cleaned):
            return RoutingDecision(
                profile=RouteProfile.REMINDER,
                confidence=0.75,
                reason="reminder intent",
                vector=ModulationVector(warmth=0.55, verbosity=0.25, technical_precision=0.75, structure=0.55, temperature_hint=0.3),
            )

        if _SUPPORT_RE.search(cleaned):
            return RoutingDecision(
                profile=RouteProfile.SUPPORT,
                confidence=0.78,
                reason="support signal",
                vector=ModulationVector(
                    warmth=0.8 + relation_bonus,
                    verbosity=0.35,
                    technical_precision=0.35,
                    playfulness=0.05,
                    intimacy=0.35 + relation_bonus,
                    structure=0.3,
                    temperature_hint=0.55,
                ).clamp(),
            )

        if _RP_RE.search(cleaned):
            return RoutingDecision(
                profile=RouteProfile.RP,
                confidence=0.78,
                reason="rp/body-language signal",
                vector=ModulationVector(
                    warmth=0.82 + relation_bonus,
                    verbosity=0.65,
                    technical_precision=0.2,
                    playfulness=0.35,
                    intimacy=0.45 + relation_bonus,
                    structure=0.25,
                    temperature_hint=0.85,
                ).clamp(),
            )

        if _TECHNICAL_RE.search(cleaned):
            return RoutingDecision(
                profile=RouteProfile.TECHNICAL,
                confidence=0.75,
                reason="technical keywords",
                vector=ModulationVector(
                    warmth=max(0.48, 0.55 - fatigue * 0.1),
                    verbosity=0.65,
                    technical_precision=0.9,
                    playfulness=0.1,
                    intimacy=0.15 + relation_bonus,
                    structure=0.85,
                    temperature_hint=0.4,
                ).clamp(),
            )

        if _RESEARCH_RE.search(cleaned):
            return RoutingDecision(
                profile=RouteProfile.RESEARCH,
                confidence=0.7,
                reason="research/review intent",
                vector=ModulationVector(warmth=0.5, verbosity=0.8, technical_precision=0.7, structure=0.85, temperature_hint=0.45),
            )

        return RoutingDecision(
            profile=RouteProfile.DEFAULT,
            confidence=0.45,
            reason="default conversation",
            vector=ModulationVector(
                warmth=0.62 + relation_bonus,
                verbosity=max(0.35, 0.5 - fatigue * 0.15),
                technical_precision=0.45,
                playfulness=0.2,
                intimacy=0.25 + relation_bonus,
                structure=0.45,
                temperature_hint=0.75,
            ).clamp(),
        )
