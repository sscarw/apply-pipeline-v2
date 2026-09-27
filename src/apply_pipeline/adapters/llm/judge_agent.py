from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from apply_pipeline.adapters.llm.prompts import load_rules, render_profile
from apply_pipeline.adapters.llm.schemas import JudgeOutput
from apply_pipeline.domain.models import Vacancy
from apply_pipeline.domain.profile import CandidateProfile
from apply_pipeline.domain.user import Language


@dataclass(frozen=True, slots=True)
class JudgeDeps:
    profile: CandidateProfile
    language: Language


def vacancy_to_prompt(
    vacancy: Vacancy,
    *,
    max_chars: int = 6000,
) -> str:
    location = vacancy.location or "not specified"
    salary = vacancy.salary_text or "not specified"
    published_at = vacancy.published_at.isoformat()
    description = vacancy.description[:max_chars] or "not specified"

    return (
        f"Position: {vacancy.title}\n"
        f"Company: {vacancy.company}\n"
        f"Location: {location}\n"
        f"Salary: {salary}\n"
        f"Published: {published_at}\n"
        f"\n"
        f"{description}"
    )


def build_judge_agent(
    model: Model,
) -> Agent[JudgeDeps, JudgeOutput]:
    agent = Agent(
        model=model,
        deps_type=JudgeDeps,
        output_type=JudgeOutput,
        instructions=load_rules(),
        model_settings=ModelSettings(
            temperature=0,
        ),
        retries=1,
    )

    @agent.instructions
    def profile_instructions(
        ctx: RunContext[JudgeDeps],
    ) -> str:
        return render_profile(
            ctx.deps.profile,
            ctx.deps.language,
        )

    return agent
