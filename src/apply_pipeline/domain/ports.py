from typing import Protocol

from apply_pipeline.domain.judge import JudgeVerdict
from apply_pipeline.domain.models import Vacancy


class VacancyJudge(Protocol):
    """Decides whether a vacancy is worth applying to.

    Services depend on this port rather than on LangGraph or a model provider,
    so the LLM judge can be swapped for a fake in tests.
    """

    async def judge(self, vacancy: Vacancy) -> JudgeVerdict:
        """Read the vacancy and return the verdict.

        Never raises because a model is unavailable: in that case the verdict
        lets the vacancy through with fail_open=True.
        """
        ...
