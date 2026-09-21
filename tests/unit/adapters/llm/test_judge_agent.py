from dataclasses import replace

from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from apply_pipeline.adapters.llm.judge_agent import build_judge_agent, vacancy_to_prompt
from apply_pipeline.adapters.llm.prompts import build_judge_instructions
from apply_pipeline.adapters.llm.schemas import JudgeOutput
from apply_pipeline.domain.models import Vacancy


def test_prompt_contains_vacancy_fields(vacancy: Vacancy) -> None:
    prompt = vacancy_to_prompt(vacancy)

    assert "Python Engineer" in prompt
    assert "Broscorp" in prompt
    assert "Remote, UA" in prompt
    assert "$1000-1500" in prompt
    assert "2026-09-01" in prompt
    assert prompt.endswith(vacancy.description)


def test_prompt_separates_header_from_description(vacancy: Vacancy) -> None:
    prompt = vacancy_to_prompt(vacancy)

    assert f"\n\n{vacancy.description}" in prompt


def test_prompt_marks_missing_fields(vacancy: Vacancy) -> None:
    prompt = vacancy_to_prompt(replace(vacancy, location=None, salary_text=None))

    assert "Location: not specified" in prompt
    assert "Salary: not specified" in prompt


def test_prompt_truncates_long_description(vacancy: Vacancy) -> None:
    long_vacancy = replace(vacancy, description="a" * 100 + "TAIL")

    prompt = vacancy_to_prompt(long_vacancy, max_chars=100)

    assert "a" * 100 in prompt
    assert "TAIL" not in prompt


async def test_agent_returns_structured_output(vacancy: Vacancy) -> None:
    model = TestModel(custom_output_args={"apply": True, "reason": "Python і LLM", "gaps": []})
    agent = build_judge_agent(model)

    result = await agent.run(vacancy_to_prompt(vacancy))

    assert result.output == JudgeOutput(apply=True, reason="Python і LLM", gaps=[])


async def test_agent_sends_instructions_and_zero_temperature(vacancy: Vacancy) -> None:
    seen: list[AgentInfo] = []

    def answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.append(info)
        tool = info.output_tools[0]
        args = {"apply": False, "reason": "Основна мова C#", "gaps": []}
        return ModelResponse(parts=[ToolCallPart(tool.name, args)])

    agent = build_judge_agent(FunctionModel(answer))

    await agent.run(vacancy_to_prompt(vacancy))

    # Pydantic AI strips surrounding whitespace from instructions.
    assert seen[0].instructions == build_judge_instructions().strip()
    assert seen[0].model_settings is not None
    assert seen[0].model_settings.get("temperature") == 0
