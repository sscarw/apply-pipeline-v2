from typing import Any

import pytest
from pydantic_ai.exceptions import ModelAPIError
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models import Model
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from apply_pipeline.adapters.llm.judge_agent import build_judge_agent
from apply_pipeline.adapters.llm.judge_graph import (
    JudgeState,
    LangGraphVacancyJudge,
    build_judge_graph,
    route_after_call,
)
from apply_pipeline.adapters.llm.prompts import JUDGE_PROMPT_VERSION
from apply_pipeline.adapters.llm.schemas import JudgeOutput
from apply_pipeline.domain.models import Vacancy
from apply_pipeline.domain.ports import VacancyJudge


def _answering_model(**output: Any) -> TestModel:
    return TestModel(custom_output_args={"reason": "Python і LLM", "gaps": [], **output})


def _broken_model(name: str) -> FunctionModel:
    def fail(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise ModelAPIError(name, "503 Service Unavailable")

    return FunctionModel(fail, model_name=name)


def _judge(model: Model) -> LangGraphVacancyJudge:
    return LangGraphVacancyJudge(build_judge_graph(build_judge_agent(model)))


def test_judge_satisfies_port() -> None:
    judge: VacancyJudge = _judge(_answering_model(apply=True))

    assert isinstance(judge, LangGraphVacancyJudge)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"output": JudgeOutput(apply=False, reason="C#")}, "finalize"),
        ({"output": None, "error": "timeout"}, "fail_open"),
        ({}, "fail_open"),
    ],
)
def test_route_after_call(state: JudgeState, expected: str) -> None:
    assert route_after_call(state) == expected


async def test_model_answer_becomes_verdict(vacancy: Vacancy) -> None:
    judge = _judge(_answering_model(apply=True, gaps=["Django", "AWS"]))

    verdict = await judge.judge(vacancy)

    assert verdict.apply is True
    assert verdict.reason == "Python і LLM"
    assert verdict.gaps == ("Django", "AWS")
    assert verdict.prompt_version == JUDGE_PROMPT_VERSION
    assert verdict.fail_open is False


async def test_negative_answer_is_not_fail_open(vacancy: Vacancy) -> None:
    judge = _judge(_answering_model(apply=False))

    verdict = await judge.judge(vacancy)

    assert verdict.apply is False
    assert verdict.fail_open is False


async def test_unavailable_model_lets_vacancy_through(vacancy: Vacancy) -> None:
    judge = _judge(_broken_model("primary"))

    verdict = await judge.judge(vacancy)

    assert verdict.apply is True
    assert verdict.fail_open is True
    assert verdict.gaps == ()
    assert verdict.prompt_version == JUDGE_PROMPT_VERSION


async def test_invalid_output_after_retries_lets_vacancy_through(vacancy: Vacancy) -> None:
    # reason is longer than 200 characters on every attempt, so the agent gives up.
    judge = _judge(_answering_model(apply=False, reason="x" * 201))

    verdict = await judge.judge(vacancy)

    assert verdict.fail_open is True


async def test_fallback_model_answers_when_primary_fails(vacancy: Vacancy) -> None:
    model = FallbackModel(_broken_model("primary"), _answering_model(apply=False))

    verdict = await _judge(model).judge(vacancy)

    assert verdict.apply is False
    assert verdict.fail_open is False


async def test_all_fallback_models_failing_lets_vacancy_through(vacancy: Vacancy) -> None:
    model = FallbackModel(_broken_model("primary"), _broken_model("fallback"))

    verdict = await _judge(model).judge(vacancy)

    assert verdict.fail_open is True
