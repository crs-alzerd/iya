from __future__ import annotations

from iya_bot.application.ports import WorkflowEngine
from iya_bot.domain.enums import WorkflowStepStatus
from iya_bot.domain.models import WorkflowStep


class DeterministicWorkflowEngine(WorkflowEngine):
    """Mock-движок координации: раскладывает цель на фиксированные шаги.

    Замена реального движка (например, поверх ModelProvider/nanogpt) на время
    сборки фундамента. Поведение детерминировано, чтобы бизнес-логику можно было
    тестировать без LLM.
    """

    def __init__(self, template: list[str] | None = None) -> None:
        # Универсальный каркас координации действия.
        self._template = template or ["Прояснить цель", "Разбить на шаги", "Запланировать", "Выполнить", "Проверить результат"]

    async def plan(self, goal: str, context: str | None = None) -> list[WorkflowStep]:
        steps = [WorkflowStep(title=f"{phase}: {goal}", status=WorkflowStepStatus.PENDING) for phase in self._template]
        if steps:
            steps[0] = WorkflowStep(title=steps[0].title, status=WorkflowStepStatus.IN_PROGRESS)
        return steps

    async def advance(self, steps: list[WorkflowStep], done_title: str) -> list[WorkflowStep]:
        updated: list[WorkflowStep] = []
        marked_next = False
        for step in steps:
            if step.title == done_title:
                updated.append(WorkflowStep(title=step.title, status=WorkflowStepStatus.DONE, detail=step.detail, scheduled_for=step.scheduled_for))
                continue
            updated.append(step)
        # Перевести первый ещё не выполненный шаг в работу.
        for index, step in enumerate(updated):
            if step.status in (WorkflowStepStatus.DONE, WorkflowStepStatus.SKIPPED):
                continue
            if not marked_next:
                updated[index] = WorkflowStep(
                    title=step.title,
                    status=WorkflowStepStatus.IN_PROGRESS,
                    detail=step.detail,
                    scheduled_for=step.scheduled_for,
                )
                marked_next = True
        return updated
