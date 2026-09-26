import pytest

from apply_pipeline.domain.criteria import (
    Criterion,
    CriterionResult,
    CriterionStatus,
    Priority,
)
from apply_pipeline.domain.errors import ScoringError
from apply_pipeline.domain.scoring import WEIGHTS, MatchScore, score_match

MET = CriterionStatus.MET
NOT_MET = CriterionStatus.NOT_MET
UNKNOWN = CriterionStatus.UNKNOWN


def _criterion(criterion_id: str, priority: Priority) -> Criterion:
    return Criterion(criterion_id, f"Criterion {criterion_id}", priority)


def _result(criterion_id: str, status: CriterionStatus) -> CriterionResult:
    evidence = None if status == UNKNOWN else f"quote for {criterion_id}"
    return CriterionResult(criterion_id, status, evidence=evidence)


# The worked example from the Day 5 ticket.
EXAMPLE_CRITERIA = (
    _criterion("python", Priority.MUST),
    _criterion("no_senior", Priority.MUST),
    _criterion("remote", Priority.MUST),
    _criterion("no_crypto", Priority.EXCLUDE),
    _criterion("llm", Priority.IMPORTANT),
    _criterion("fastapi", Priority.NICE),
)


def _example_results(*, no_crypto: CriterionStatus = NOT_MET) -> list[CriterionResult]:
    return [
        _result("python", MET),
        _result("no_senior", MET),
        _result("remote", UNKNOWN),
        _result("no_crypto", no_crypto),
        _result("llm", MET),
        _result("fastapi", NOT_MET),
    ]


def test_weights() -> None:
    assert dict(WEIGHTS) == {Priority.MUST: 3, Priority.IMPORTANT: 2, Priority.NICE: 1}


def test_weights_are_read_only() -> None:
    with pytest.raises(TypeError):
        WEIGHTS[Priority.EXCLUDE] = 5  # type: ignore[index]


def test_ticket_example() -> None:
    score = score_match(EXAMPLE_CRITERIA, _example_results())

    assert score == MatchScore(value=79, blocked_by=(), scored_count=5, unknown_count=1)
    assert not score.is_blocked


def test_ticket_example_blocked_by_exclude() -> None:
    score = score_match(EXAMPLE_CRITERIA, _example_results(no_crypto=MET))

    assert score.value == 0
    assert score.blocked_by == ("no_crypto",)
    assert score.is_blocked
    assert score.scored_count == 5
    assert score.unknown_count == 1


@pytest.mark.parametrize(
    ("status", "expected"),
    [(MET, 100), (UNKNOWN, 50), (NOT_MET, 0)],
    ids=["met", "unknown", "not-met"],
)
@pytest.mark.parametrize("priority", [Priority.IMPORTANT, Priority.NICE])
def test_single_soft_criterion(priority: Priority, status: CriterionStatus, expected: int) -> None:
    score = score_match([_criterion("x", priority)], [_result("x", status)])

    assert score.value == expected
    assert not score.is_blocked


def test_not_met_important_lowers_score_without_blocking() -> None:
    criteria = [_criterion("python", Priority.MUST), _criterion("llm", Priority.IMPORTANT)]

    score = score_match(criteria, [_result("python", MET), _result("llm", NOT_MET)])

    assert score.value == 60
    assert not score.is_blocked


def test_not_met_must_blocks() -> None:
    criteria = [_criterion("python", Priority.MUST), _criterion("llm", Priority.IMPORTANT)]

    score = score_match(criteria, [_result("python", NOT_MET), _result("llm", MET)])

    assert score.value == 0
    assert score.blocked_by == ("python",)


def test_unknown_must_does_not_block() -> None:
    score = score_match([_criterion("python", Priority.MUST)], [_result("python", UNKNOWN)])

    assert score.value == 50
    assert not score.is_blocked


@pytest.mark.parametrize("status", [NOT_MET, UNKNOWN], ids=["not-met", "unknown"])
def test_exclude_that_is_not_met_changes_nothing(status: CriterionStatus) -> None:
    llm = _criterion("llm", Priority.IMPORTANT)
    without_exclude = score_match([llm], [_result("llm", MET)])

    with_exclude = score_match(
        [llm, _criterion("no_crypto", Priority.EXCLUDE)],
        [_result("llm", MET), _result("no_crypto", status)],
    )

    assert with_exclude == without_exclude


def test_ignored_criterion_changes_nothing() -> None:
    llm = _criterion("llm", Priority.IMPORTANT)
    without_ignored = score_match([llm], [_result("llm", MET)])

    with_ignored = score_match(
        [llm, _criterion("office", Priority.IGNORE)],
        [_result("llm", MET), _result("office", NOT_MET)],
    )

    assert with_ignored == without_ignored


def test_ignored_must_like_criterion_never_blocks() -> None:
    criteria = [_criterion("llm", Priority.NICE), _criterion("python", Priority.IGNORE)]

    score = score_match(criteria, [_result("llm", MET), _result("python", NOT_MET)])

    assert score.value == 100


def test_blocked_by_keeps_profile_order() -> None:
    criteria = [
        _criterion("gambling", Priority.EXCLUDE),
        _criterion("python", Priority.MUST),
        _criterion("crypto", Priority.EXCLUDE),
    ]
    results = [
        _result("crypto", MET),
        _result("python", NOT_MET),
        _result("gambling", MET),
    ]

    score = score_match(criteria, results)

    assert score.blocked_by == ("gambling", "python", "crypto")


def test_missing_result_counts_as_unknown() -> None:
    criteria = [_criterion("python", Priority.MUST), _criterion("remote", Priority.MUST)]

    score = score_match(criteria, [_result("python", MET)])

    assert score.value == 75
    assert score.unknown_count == 1


def test_no_results_at_all() -> None:
    score = score_match(EXAMPLE_CRITERIA, [])

    assert score.value == 50
    assert score.unknown_count == score.scored_count == 5
    assert not score.is_blocked


def test_duplicate_result_raises() -> None:
    criteria = [_criterion("python", Priority.MUST)]

    with pytest.raises(ScoringError, match="python"):
        score_match(criteria, [_result("python", MET), _result("python", NOT_MET)])


def test_result_for_unknown_criterion_raises() -> None:
    criteria = [_criterion("python", Priority.MUST)]

    with pytest.raises(ScoringError, match="kotlin"):
        score_match(criteria, [_result("python", MET), _result("kotlin", MET)])


@pytest.mark.parametrize(
    "criteria",
    [
        [],
        [_criterion("no_crypto", Priority.EXCLUDE)],
        [_criterion("office", Priority.IGNORE)],
    ],
    ids=["no-criteria", "only-exclude", "only-ignore"],
)
def test_no_scoring_criteria_raises(criteria: list[Criterion]) -> None:
    with pytest.raises(ScoringError):
        score_match(criteria, [])


ROUNDING_CASES = [
    # 1 of 8 half-units = 12.5: rounds up to 13, while round(12.5) would give 12.
    ([(Priority.NICE, UNKNOWN)] + [(Priority.NICE, NOT_MET)] * 3, 13),
    # 2 of 6 half-units = 33.33: rounds down.
    ([(Priority.IMPORTANT, UNKNOWN), (Priority.NICE, NOT_MET)], 33),
    # 4 of 6 half-units = 66.67: rounds up.
    ([(Priority.IMPORTANT, MET), (Priority.NICE, NOT_MET)], 67),
]


@pytest.mark.parametrize(
    ("cases", "expected"),
    ROUNDING_CASES,
    ids=["exact-half-rounds-up", "third-rounds-down", "two-thirds-rounds-up"],
)
def test_rounding(cases: list[tuple[Priority, CriterionStatus]], expected: int) -> None:
    criteria = [_criterion(f"c{index}", priority) for index, (priority, _) in enumerate(cases)]
    results = [_result(f"c{index}", status) for index, (_, status) in enumerate(cases)]

    assert score_match(criteria, results).value == expected


def test_builtin_round_is_bankers_rounding() -> None:
    # The reason score_match rounds with integers instead of round().
    assert round(12.5) == 12
    assert round(78.5) == 78


@pytest.mark.parametrize(
    "kwargs",
    [
        {"value": -1},
        {"value": 101},
        {"value": 50, "blocked_by": ("python",)},
        {"scored_count": -1, "unknown_count": 0},
        {"unknown_count": -1},
        {"scored_count": 1, "unknown_count": 2},
    ],
    ids=[
        "negative-value",
        "value-over-100",
        "blocked-but-not-zero",
        "negative-scored-count",
        "negative-unknown-count",
        "more-unknown-than-scored",
    ],
)
def test_invalid_match_score_raises(kwargs: dict[str, object]) -> None:
    values: dict[str, object] = {
        "value": 0,
        "blocked_by": (),
        "scored_count": 3,
        "unknown_count": 1,
        **kwargs,
    }

    with pytest.raises(ScoringError):
        MatchScore(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [0, 100])
def test_match_score_bounds_are_inclusive(value: int) -> None:
    assert MatchScore(value=value, blocked_by=(), scored_count=1, unknown_count=0).value == value
