from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from apply_pipeline.domain.criteria import Criterion, Priority
from apply_pipeline.domain.errors import InvalidProfileError
from apply_pipeline.domain.profile import (
    MAX_CRITERIA,
    CandidateProfile,
    Currency,
    Salary,
    WorkFormat,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
CREATED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)

PYTHON = Criterion("python", "Основна мова роботи Python", Priority.MUST)
NO_CRYPTO = Criterion("no_crypto", "Криптовалюти, Web3", Priority.EXCLUDE)


def _make_profile(**overrides: Any) -> CandidateProfile:
    values: dict[str, Any] = {
        "user_id": USER_ID,
        "version": 1,
        "created_at": CREATED_AT,
        "desired_roles": ("Junior Python Developer",),
        "experience_years": 0,
        "skills": ("Python", "FastAPI"),
        "work_formats": frozenset({WorkFormat.REMOTE}),
        "criteria": (PYTHON, NO_CRYPTO),
        **overrides,
    }
    return CandidateProfile(**values)


def _criteria(count: int, priority: Priority = Priority.NICE) -> tuple[Criterion, ...]:
    return tuple(Criterion(f"c{index}", f"Criterion {index}", priority) for index in range(count))


def test_valid_profile() -> None:
    profile = _make_profile(min_salary=Salary(500, Currency.USD))

    assert profile.version == 1
    assert profile.city is None
    assert profile.min_salary == Salary(500, Currency.USD)


def test_profile_is_frozen() -> None:
    profile = _make_profile()

    with pytest.raises(FrozenInstanceError):
        profile.version = 2  # type: ignore[misc]


@pytest.mark.parametrize("amount", [0, -500])
def test_salary_must_be_positive(amount: int) -> None:
    with pytest.raises(InvalidProfileError):
        Salary(amount, Currency.UAH)


INVALID_PROFILES: list[dict[str, Any]] = [
    {"version": 0},
    {"created_at": datetime(2026, 9, 1, 12, 0)},
    {"desired_roles": ()},
    {"desired_roles": ("Python Developer", "  ")},
    {"experience_years": -1},
    {"experience_years": 61},
    {"work_formats": frozenset()},
    {"work_formats": frozenset({WorkFormat.OFFICE})},
    {"work_formats": frozenset({WorkFormat.HYBRID}), "city": "   "},
    {"criteria": _criteria(MAX_CRITERIA + 1)},
    {"criteria": (PYTHON, Criterion("python", "Python again", Priority.NICE))},
    {"criteria": (NO_CRYPTO,)},
    {"criteria": (NO_CRYPTO, Criterion("remote", "Remote", Priority.IGNORE))},
    {"criteria": ()},
]

INVALID_PROFILE_IDS = [
    "version-zero",
    "naive-created-at",
    "no-roles",
    "blank-role",
    "negative-experience",
    "experience-over-60",
    "no-work-format",
    "office-without-city",
    "hybrid-with-blank-city",
    "too-many-criteria",
    "duplicate-criterion-ids",
    "only-exclude-criteria",
    "only-exclude-and-ignore",
    "no-criteria",
]


@pytest.mark.parametrize("overrides", INVALID_PROFILES, ids=INVALID_PROFILE_IDS)
def test_invalid_profile_raises_error(overrides: dict[str, Any]) -> None:
    with pytest.raises(InvalidProfileError):
        _make_profile(**overrides)


def test_office_with_city_is_valid() -> None:
    profile = _make_profile(
        work_formats=frozenset({WorkFormat.OFFICE, WorkFormat.REMOTE}),
        city="Львів",
    )

    assert profile.city == "Львів"


@pytest.mark.parametrize("experience_years", [0, 60])
def test_experience_bounds_are_inclusive(experience_years: int) -> None:
    assert _make_profile(experience_years=experience_years).experience_years == experience_years


def test_exactly_max_criteria_is_allowed() -> None:
    assert len(_make_profile(criteria=_criteria(MAX_CRITERIA)).criteria) == MAX_CRITERIA


@pytest.mark.parametrize("priority", [Priority.MUST, Priority.IMPORTANT, Priority.NICE])
def test_any_scoring_priority_is_enough(priority: Priority) -> None:
    _make_profile(criteria=(NO_CRYPTO, Criterion("llm", "LLM", priority)))


def test_revise_creates_next_version() -> None:
    profile = _make_profile()

    revised = profile.revise(now=LATER, desired_roles=("AI Engineer",))

    assert revised.version == 2
    assert revised.created_at == LATER
    assert revised.desired_roles == ("AI Engineer",)
    assert revised.user_id == profile.user_id
    assert revised.criteria == profile.criteria


def test_revise_keeps_old_version_unchanged() -> None:
    profile = _make_profile()

    profile.revise(now=LATER, experience_years=2)

    assert profile.version == 1
    assert profile.experience_years == 0
    assert profile.created_at == CREATED_AT


def test_revise_can_be_chained() -> None:
    profile = _make_profile().revise(now=LATER).revise(now=LATER)

    assert profile.version == 3


def test_revise_runs_validation_again() -> None:
    profile = _make_profile()

    with pytest.raises(InvalidProfileError):
        profile.revise(now=LATER, work_formats=frozenset({WorkFormat.OFFICE}))


def test_revise_rejects_naive_now() -> None:
    with pytest.raises(InvalidProfileError):
        _make_profile().revise(now=datetime(2026, 9, 5, 12, 0))


@pytest.mark.parametrize(
    "changes",
    [
        {"version": 10},
        {"created_at": LATER},
        {"user_id": UUID("00000000-0000-0000-0000-000000000002")},
    ],
    ids=["version", "created-at", "user-id"],
)
def test_revise_rejects_managed_fields(changes: dict[str, Any]) -> None:
    with pytest.raises(InvalidProfileError):
        _make_profile().revise(now=LATER, **changes)


def test_revise_rejects_unknown_field() -> None:
    with pytest.raises(TypeError):
        _make_profile().revise(now=LATER, favourite_colour="blue")
