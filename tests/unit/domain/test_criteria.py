import pytest

from apply_pipeline.domain.criteria import (
    Criterion,
    CriterionResult,
    CriterionStatus,
    Priority,
)
from apply_pipeline.domain.errors import InvalidProfileError, ScoringError


def test_valid_criterion() -> None:
    criterion = Criterion(id="python", text="Основна мова роботи Python", priority=Priority.MUST)

    assert criterion.priority == Priority.MUST


def test_enum_values_are_lowercase() -> None:
    # These strings are stored in the database and returned by the judge.
    assert [priority.value for priority in Priority] == [
        "must",
        "important",
        "nice",
        "exclude",
        "ignore",
    ]
    assert [status.value for status in CriterionStatus] == ["met", "not_met", "unknown"]


@pytest.mark.parametrize(
    ("criterion_id", "text"),
    [
        ("", "Python"),
        ("   ", "Python"),
        ("x" * 65, "Python"),
        ("no crypto", "Python"),
        ("no\tcrypto", "Python"),
        ("python", ""),
        ("python", "   "),
        ("python", "x" * 301),
    ],
    ids=[
        "empty-id",
        "whitespace-id",
        "id-too-long",
        "id-with-space",
        "id-with-tab",
        "empty-text",
        "whitespace-text",
        "text-too-long",
    ],
)
def test_invalid_criterion_raises_error(criterion_id: str, text: str) -> None:
    with pytest.raises(InvalidProfileError):
        Criterion(id=criterion_id, text=text, priority=Priority.MUST)


def test_criterion_limits_are_inclusive() -> None:
    Criterion(id="x" * 64, text="x" * 300, priority=Priority.NICE)


@pytest.mark.parametrize("status", [CriterionStatus.MET, CriterionStatus.NOT_MET])
def test_decided_result_keeps_evidence(status: CriterionStatus) -> None:
    result = CriterionResult("python", status, evidence="Python 3.12, FastAPI")

    assert result.evidence == "Python 3.12, FastAPI"


@pytest.mark.parametrize("status", [CriterionStatus.MET, CriterionStatus.NOT_MET])
@pytest.mark.parametrize("evidence", [None, "", "   "], ids=["none", "empty", "whitespace"])
def test_decided_result_requires_evidence(status: CriterionStatus, evidence: str | None) -> None:
    with pytest.raises(ScoringError):
        CriterionResult("python", status, evidence=evidence)


def test_unknown_result_without_evidence() -> None:
    result = CriterionResult("remote", CriterionStatus.UNKNOWN)

    assert result.evidence is None


@pytest.mark.parametrize("evidence", ["Remote", ""], ids=["quote", "empty-string"])
def test_unknown_result_rejects_evidence(evidence: str) -> None:
    with pytest.raises(ScoringError):
        CriterionResult("remote", CriterionStatus.UNKNOWN, evidence=evidence)
