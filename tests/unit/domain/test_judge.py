from collections.abc import Callable
from decimal import Decimal

import pytest

from apply_pipeline.domain.criteria import CriterionResult, CriterionStatus
from apply_pipeline.domain.errors import InvalidVerdictError
from apply_pipeline.domain.judge import JudgeFailure, JudgeUsage, JudgeVerdict

UNAVAILABLE = JudgeFailure.UNAVAILABLE
INVALID_OUTPUT = JudgeFailure.INVALID_OUTPUT

USAGE = JudgeUsage("gpt-4.1-mini", 1400, 300, 1024, Decimal("0.0011"))
RESULTS = (CriterionResult("python", CriterionStatus.MET, "Python 3.13"),)


def test_failure_values_are_lowercase() -> None:
    # Stored in the database next to every decision.
    assert [failure.value for failure in JudgeFailure] == ["unavailable", "invalid_output"]


def test_judged_verdict() -> None:
    verdict = JudgeVerdict(RESULTS, "Python і LLM.", "judge_v2", USAGE, None, 2)

    assert verdict.fail_open is False
    assert verdict.discarded == 2


def test_unavailable_verdict_is_free() -> None:
    verdict = JudgeVerdict((), None, "judge_v2", None, UNAVAILABLE, 0)

    assert verdict.fail_open is True
    assert verdict.usage is None


def test_invalid_output_keeps_its_cost() -> None:
    verdict = JudgeVerdict((), None, "judge_v2", USAGE, INVALID_OUTPUT, 0)

    assert verdict.fail_open is True
    assert verdict.usage == USAGE


def test_usage_without_known_price() -> None:
    assert JudgeUsage("my-local-model", 10, 5, 0, None).cost_usd is None


INVALID_USAGES: dict[str, Callable[[], JudgeUsage]] = {
    "empty-model-name": lambda: JudgeUsage("  ", 1, 1, 0, None),
    "negative-input": lambda: JudgeUsage("m", -1, 1, 0, None),
    "negative-output": lambda: JudgeUsage("m", 1, -1, 0, None),
    "negative-cache": lambda: JudgeUsage("m", 1, 1, -1, None),
    "negative-cost": lambda: JudgeUsage("m", 1, 1, 0, Decimal("-0.000001")),
}


@pytest.mark.parametrize("make", INVALID_USAGES.values(), ids=INVALID_USAGES.keys())
def test_invalid_usage_raises(make: Callable[[], JudgeUsage]) -> None:
    with pytest.raises(InvalidVerdictError):
        make()


INVALID_VERDICTS: dict[str, Callable[[], JudgeVerdict]] = {
    "empty-prompt-version": lambda: JudgeVerdict(RESULTS, "s", " ", USAGE, None, 0),
    "negative-discarded": lambda: JudgeVerdict(RESULTS, "s", "v", USAGE, None, -1),
    "judged-without-summary": lambda: JudgeVerdict(RESULTS, None, "v", USAGE, None, 0),
    "judged-blank-summary": lambda: JudgeVerdict(RESULTS, "  ", "v", USAGE, None, 0),
    "judged-without-usage": lambda: JudgeVerdict(RESULTS, "s", "v", None, None, 0),
    "failed-with-results": lambda: JudgeVerdict(RESULTS, None, "v", None, UNAVAILABLE, 0),
    "failed-with-summary": lambda: JudgeVerdict((), "s", "v", USAGE, INVALID_OUTPUT, 0),
    "failed-with-discarded": lambda: JudgeVerdict((), None, "v", None, UNAVAILABLE, 1),
    "unavailable-with-usage": lambda: JudgeVerdict((), None, "v", USAGE, UNAVAILABLE, 0),
    "billed-failure-without-usage": lambda: JudgeVerdict((), None, "v", None, INVALID_OUTPUT, 0),
}


@pytest.mark.parametrize("make", INVALID_VERDICTS.values(), ids=INVALID_VERDICTS.keys())
def test_invalid_verdict_raises(make: Callable[[], JudgeVerdict]) -> None:
    with pytest.raises(InvalidVerdictError):
        make()
