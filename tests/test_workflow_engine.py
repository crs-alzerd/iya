from iya_bot.domain.enums import WorkflowStepStatus
from iya_bot.infrastructure.workflow.mock import DeterministicWorkflowEngine


async def test_plan_produces_steps_with_first_in_progress():
    engine = DeterministicWorkflowEngine(template=["Шаг A", "Шаг B", "Шаг C"])

    steps = await engine.plan("выучить испанский")

    assert [s.title for s in steps] == ["Шаг A: выучить испанский", "Шаг B: выучить испанский", "Шаг C: выучить испанский"]
    assert steps[0].status == WorkflowStepStatus.IN_PROGRESS
    assert steps[1].status == WorkflowStepStatus.PENDING


async def test_advance_marks_done_and_moves_next_into_progress():
    engine = DeterministicWorkflowEngine(template=["A", "B", "C"])
    steps = await engine.plan("цель")

    advanced = await engine.advance(steps, done_title="A: цель")

    assert advanced[0].status == WorkflowStepStatus.DONE
    assert advanced[1].status == WorkflowStepStatus.IN_PROGRESS
    assert advanced[2].status == WorkflowStepStatus.PENDING
