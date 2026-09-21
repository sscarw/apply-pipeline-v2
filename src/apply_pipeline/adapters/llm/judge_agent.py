from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from apply_pipeline.adapters.llm.prompts import build_judge_instructions
from apply_pipeline.adapters.llm.schemas import JudgeOutput
from apply_pipeline.domain.models import Vacancy


def vacancy_to_prompt(vacancy: Vacancy, *, max_chars: int = 6000) -> str:
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


def build_judge_agent(model: Model) -> Agent[None, JudgeOutput]:
    return Agent(
        model=model,
        output_type=JudgeOutput,
        instructions=build_judge_instructions(),
        model_settings=ModelSettings(temperature=0),
        retries=2,
    )
