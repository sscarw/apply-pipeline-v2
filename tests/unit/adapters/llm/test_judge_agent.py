from dataclasses import replace

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from apply_pipeline.adapters.llm.judge_agent import JudgeDeps, build_judge_agent, vacancy_to_prompt
from apply_pipeline.adapters.llm.prompts import load_rules, render_profile
from apply_pipeline.adapters.llm.schemas import CriterionAnswer, JudgeOutput
from apply_pipeline.domain.criteria import CriterionStatus
from apply_pipeline.domain.models import Vacancy
from apply_pipeline.domain.profile import CandidateProfile
from apply_pipeline.domain.user import Language


def test_prompt_contains_vacancy_fields(vacancy: Vacancy) -> None:
    prompt = vacancy_to_prompt(vacancy)

    assert "Position: Python Engineer" in prompt
    assert "Company: Broscorp" in prompt
    assert "Location: Remote, UA" in prompt
    assert "Salary: $1000-1500" in prompt
    assert "2026-09-01" in prompt
    assert prompt.endswith(vacancy.description)


def test_prompt_separates_header_from_description(vacancy: Vacancy) -> None:
    assert f"\n\n{vacancy.description}" in vacancy_to_prompt(vacancy)


def test_prompt_marks_missing_fields(vacancy: Vacancy) -> None:
    prompt = vacancy_to_prompt(replace(vacancy, location=None, salary_text=None))

    assert "Location: not specified" in prompt
    assert "Salary: not specified" in prompt


def test_prompt_truncates_long_description(vacancy: Vacancy) -> None:
    prompt = vacancy_to_prompt(replace(vacancy, description="a" * 100 + "TAIL"), max_chars=100)

    assert "a" * 100 in prompt
    assert "TAIL" not in prompt


def _deps(profile: CandidateProfile, language: Language = Language.UK) -> JudgeDeps:
    return JudgeDeps(profile=profile, language=language)


async def test_agent_returns_structured_output(vacancy: Vacancy, profile: CandidateProfile) -> None:
    answers = [{"criterion_id": "python", "status": "met", "evidence": "in Python"}]
    model = TestModel(custom_output_args={"answers": answers, "summary": "Python і LLM."})

    result = await build_judge_agent(model).run(vacancy_to_prompt(vacancy), deps=_deps(profile))

    assert result.output == JudgeOutput(
        answers=[
            CriterionAnswer(criterion_id="python", status=CriterionStatus.MET, evidence="in Python")
        ],
        summary="Python і LLM.",
    )


def _capturing_model(seen: list[AgentInfo]) -> FunctionModel:
    def answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.append(info)
        args = {"answers": [], "summary": "Summary."}
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])

    return FunctionModel(answer)


async def test_rules_come_first_then_profile(vacancy: Vacancy, profile: CandidateProfile) -> None:
    seen: list[AgentInfo] = []

    await build_judge_agent(_capturing_model(seen)).run(
        vacancy_to_prompt(vacancy), deps=_deps(profile)
    )

    instructions = seen[0].instructions
    assert instructions is not None
    rules = load_rules().strip()
    profile_text = render_profile(profile, Language.UK).strip()
    # Static rules first, then the per-user profile: the order that prompt caching needs.
    assert instructions.startswith(rules)
    assert instructions.endswith(profile_text)


async def test_vacancy_goes_in_the_user_message_not_instructions(
    vacancy: Vacancy,
    profile: CandidateProfile,
) -> None:
    seen: list[AgentInfo] = []

    await build_judge_agent(_capturing_model(seen)).run(
        vacancy_to_prompt(vacancy), deps=_deps(profile)
    )

    assert seen[0].instructions is not None
    assert vacancy.description not in seen[0].instructions


async def test_profile_follows_deps(vacancy: Vacancy, profile: CandidateProfile) -> None:
    seen: list[AgentInfo] = []
    agent = build_judge_agent(_capturing_model(seen))

    await agent.run(vacancy_to_prompt(vacancy), deps=_deps(profile, Language.UK))
    await agent.run(vacancy_to_prompt(vacancy), deps=_deps(profile, Language.EN))

    assert "Write the summary in Ukrainian." in (seen[0].instructions or "")
    assert "Write the summary in English." in (seen[1].instructions or "")


async def test_temperature_is_zero(vacancy: Vacancy, profile: CandidateProfile) -> None:
    seen: list[AgentInfo] = []

    await build_judge_agent(_capturing_model(seen)).run(
        vacancy_to_prompt(vacancy), deps=_deps(profile)
    )

    assert seen[0].model_settings is not None
    assert seen[0].model_settings.get("temperature") == 0


async def test_invalid_output_costs_at_most_two_calls(
    vacancy: Vacancy,
    profile: CandidateProfile,
) -> None:
    calls: list[int] = []

    def invalid(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(1)
        args = {"answers": [], "summary": "x" * 401}
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])

    with pytest.raises(UnexpectedModelBehavior):
        await build_judge_agent(FunctionModel(invalid)).run(
            vacancy_to_prompt(vacancy),
            deps=_deps(profile),
        )

    # The first answer plus one retry: never more paid calls than that.
    assert len(calls) == 2
