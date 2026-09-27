from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest
from pydantic_ai.exceptions import ModelAPIError
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models import Model
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage

from apply_pipeline.adapters.llm.judge_agent import build_judge_agent
from apply_pipeline.adapters.llm.judge_graph import (
    JudgeState,
    LangGraphVacancyJudge,
    build_judge_graph,
    route_after_call,
)
from apply_pipeline.adapters.llm.schemas import JudgeOutput
from apply_pipeline.domain.criteria import CriterionResult, CriterionStatus
from apply_pipeline.domain.judge import JudgeFailure, JudgeVerdict
from apply_pipeline.domain.models import Vacancy
from apply_pipeline.domain.ports import VacancyJudge
from apply_pipeline.domain.profile import CandidateProfile
from apply_pipeline.domain.user import Language

MET = CriterionStatus.MET
UNKNOWN = CriterionStatus.UNKNOWN

VALID_ANSWERS: list[dict[str, Any]] = [
    {"criterion_id": "python", "status": "met", "evidence": "agents in Python"},
    {"criterion_id": "no_crypto", "status": "unknown", "evidence": None},
    {"criterion_id": "llm", "status": "met", "evidence": "Build LLM agents"},
]

Handler = Callable[[list[ModelMessage], AgentInfo], ModelResponse]


def _responding(
    answers: list[dict[str, Any]],
    *,
    name: str = "gpt-4.1-mini",
    summary: str = "Python і LLM агенти.",
    input_tokens: int = 1500,
    cache_read_tokens: int = 1024,
) -> FunctionModel:
    def answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        args = {"answers": answers, "summary": summary}
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, args)],
            usage=RequestUsage(
                input_tokens=input_tokens,
                output_tokens=120,
                cache_read_tokens=cache_read_tokens,
            ),
        )

    return FunctionModel(answer, model_name=name)


def _down(name: str) -> FunctionModel:
    def fail(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise ModelAPIError(name, "503 Service Unavailable")

    return FunctionModel(fail, model_name=name)


def _invalid(name: str = "gpt-4.1-mini") -> FunctionModel:
    # summary longer than the schema allows: every answer is billed and rejected.
    return _responding([], name=name, summary="x" * 401)


def _judge(model: Model) -> LangGraphVacancyJudge:
    return LangGraphVacancyJudge(build_judge_graph(build_judge_agent(model)))


async def _verdict(model: Model, vacancy: Vacancy, profile: CandidateProfile) -> JudgeVerdict:
    return await _judge(model).judge(vacancy, profile, language=Language.UK)


def test_judge_satisfies_port() -> None:
    judge: VacancyJudge = _judge(_responding(VALID_ANSWERS))

    assert judge.prompt_version == "judge_v2"


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"output": JudgeOutput(answers=[], summary="s")}, "finalize"),
        ({"output": None, "failure": JudgeFailure.UNAVAILABLE}, "fail_open"),
        ({}, "fail_open"),
    ],
    ids=["answered", "failed", "empty"],
)
def test_route_after_call(state: JudgeState, expected: str) -> None:
    assert route_after_call(state) == expected


async def test_answer_becomes_checked_verdict(vacancy: Vacancy, profile: CandidateProfile) -> None:
    verdict = await _verdict(_responding(VALID_ANSWERS), vacancy, profile)

    assert verdict.results == (
        CriterionResult("python", MET, "agents in Python"),
        CriterionResult("no_crypto", UNKNOWN),
        CriterionResult("llm", MET, "Build LLM agents"),
    )
    assert verdict.summary == "Python і LLM агенти."
    assert verdict.prompt_version == "judge_v2"
    assert verdict.failure is None
    assert verdict.fail_open is False
    assert verdict.discarded == 0


async def test_usage_reaches_the_verdict(vacancy: Vacancy, profile: CandidateProfile) -> None:
    verdict = await _verdict(_responding(VALID_ANSWERS), vacancy, profile)

    assert verdict.usage is not None
    assert verdict.usage.model_name == "gpt-4.1-mini"
    assert verdict.usage.input_tokens == 1500
    assert verdict.usage.output_tokens == 120
    assert verdict.usage.cache_read_tokens == 1024
    assert verdict.usage.cost_usd is not None
    assert verdict.usage.cost_usd > 0


async def test_unknown_price_is_none_not_zero(vacancy: Vacancy, profile: CandidateProfile) -> None:
    verdict = await _verdict(_responding(VALID_ANSWERS, name="my-local-model"), vacancy, profile)

    assert verdict.usage is not None
    assert verdict.usage.cost_usd is None


async def test_invented_quote_is_downgraded_and_counted(
    vacancy: Vacancy,
    profile: CandidateProfile,
) -> None:
    answers = [*VALID_ANSWERS[:2], {"criterion_id": "llm", "status": "met", "evidence": "RAG"}]

    verdict = await _verdict(_responding(answers), vacancy, profile)

    assert verdict.results[-1] == CriterionResult("llm", UNKNOWN)
    assert verdict.discarded == 1


async def test_ignored_criterion_is_not_accepted(
    vacancy: Vacancy,
    profile: CandidateProfile,
) -> None:
    # office_only is IGNORE: it was never shown to the model, so an answer to it is invented.
    answers = [
        *VALID_ANSWERS,
        {"criterion_id": "office_only", "status": "met", "evidence": "Python"},
    ]

    verdict = await _verdict(_responding(answers), vacancy, profile)

    assert "office_only" not in {result.criterion_id for result in verdict.results}
    assert verdict.discarded == 1


async def test_quote_is_checked_against_what_the_model_saw(
    vacancy: Vacancy,
    profile: CandidateProfile,
) -> None:
    # The description is cut at 6000 characters, so a quote from its tail cannot be real.
    long_vacancy = replace(vacancy, description="Python. " + "x" * 6000 + " crypto exchange")
    answers = [{"criterion_id": "no_crypto", "status": "met", "evidence": "crypto exchange"}]

    verdict = await _verdict(_responding(answers), long_vacancy, profile)

    assert verdict.results == (CriterionResult("no_crypto", UNKNOWN),)
    assert verdict.discarded == 1


async def test_fallback_answers_when_primary_is_down(
    vacancy: Vacancy,
    profile: CandidateProfile,
) -> None:
    model = FallbackModel(_down("gpt-4.1-mini"), _responding(VALID_ANSWERS, name="gpt-4o-mini"))

    verdict = await _verdict(model, vacancy, profile)

    assert verdict.failure is None
    assert verdict.usage is not None
    assert verdict.usage.model_name == "gpt-4o-mini"


@pytest.mark.parametrize(
    "model",
    [
        pytest.param(_down("gpt-4.1-mini"), id="single-model-down"),
        pytest.param(FallbackModel(_down("gpt-4.1-mini"), _down("gpt-4o-mini")), id="both-down"),
    ],
)
async def test_nobody_answering_is_free_and_unavailable(
    model: Model,
    vacancy: Vacancy,
    profile: CandidateProfile,
) -> None:
    verdict = await _verdict(model, vacancy, profile)

    assert verdict.failure is JudgeFailure.UNAVAILABLE
    assert verdict.fail_open is True
    assert verdict.usage is None
    assert verdict.results == ()
    assert verdict.summary is None


async def test_rejected_answers_are_billed_invalid_output(
    vacancy: Vacancy,
    profile: CandidateProfile,
) -> None:
    verdict = await _verdict(_invalid(), vacancy, profile)

    assert verdict.failure is JudgeFailure.INVALID_OUTPUT
    assert verdict.usage is not None
    # Two answers were paid for: the first one and one retry.
    assert verdict.usage.input_tokens == 2 * 1500
    assert verdict.usage.model_name == "gpt-4.1-mini"
    assert verdict.usage.cost_usd is not None
    assert verdict.usage.cost_usd > Decimal("0")


async def test_billed_answer_then_outage_is_still_invalid_output(
    vacancy: Vacancy,
    profile: CandidateProfile,
) -> None:
    calls = 0
    invalid = _invalid()

    def invalid_then_down(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            assert invalid.function is not None
            return invalid.function(messages, info)  # type: ignore[return-value]
        raise ModelAPIError("gpt-4.1-mini", "503 Service Unavailable")

    model = FallbackModel(
        FunctionModel(invalid_then_down, model_name="gpt-4.1-mini"),
        _down("gpt-4o-mini"),
    )

    verdict = await _verdict(model, vacancy, profile)

    # The run ends with an outage, but one answer was already paid for:
    # retrying it automatically would spend money again.
    assert verdict.failure is JudgeFailure.INVALID_OUTPUT
    assert verdict.usage is not None
    assert verdict.usage.input_tokens == 1500
