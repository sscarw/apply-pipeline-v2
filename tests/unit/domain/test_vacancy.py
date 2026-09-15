from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone

import pytest

from apply_pipeline.domain.errors import (
    InvalidTransitionError,
    InvalidVacancyError,
)
from apply_pipeline.domain.models import StatusChange, Vacancy
from apply_pipeline.domain.transitions import (
    ALLOWED_TRANSITIONS,
    Source,
    VacancyStatus,
)

PUBLISHED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _make_vacancy(
    *,
    status: VacancyStatus = VacancyStatus.NEW,
    external_id: str = "847958",
    title: str = "Python Developer",
    company: str = "Acme",
    url: str = "https://example.com/jobs/847958",
    published_at: datetime = PUBLISHED_AT,
) -> Vacancy:
    return Vacancy(
        source=Source.DJINNI,
        external_id=external_id,
        url=url,
        title=title,
        company=company,
        description="Python backend vacancy",
        published_at=published_at,
        status=status,
    )


@pytest.fixture
def vacancy() -> Vacancy:
    return _make_vacancy()


FORBIDDEN_TRANSITIONS = [
    (VacancyStatus.NEW, VacancyStatus.OFFER),
    (VacancyStatus.NEW, VacancyStatus.NEW),
    (VacancyStatus.OFFER, VacancyStatus.SHORTLISTED),
    (VacancyStatus.REJECTED, VacancyStatus.APPLIED),
    (VacancyStatus.APPLIED, VacancyStatus.SHORTLISTED),
    (VacancyStatus.JUDGED, VacancyStatus.APPLIED),
]

FORBIDDEN_TRANSITION_IDS = [
    "new-to-offer",
    "new-to-new",
    "offer-to-shortlisted",
    "rejected-to-applied",
    "applied-to-shortlisted",
    "judged-to-applied",
]


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    FORBIDDEN_TRANSITIONS,
    ids=FORBIDDEN_TRANSITION_IDS,
)
def test_forbidden_transition_raises_error(
    from_status: VacancyStatus,
    to_status: VacancyStatus,
) -> None:
    vacancy = _make_vacancy(status=from_status)

    with pytest.raises(InvalidTransitionError) as exc_info:
        vacancy.change_status(
            to_status,
            now=datetime(2026, 9, 2, 12, 0, tzinfo=UTC),
        )

    error = exc_info.value

    assert error.from_status == from_status
    assert error.to_status == to_status
    assert str(from_status) in str(error)
    assert str(to_status) in str(error)


def test_forbidden_transition_does_not_change_vacancy() -> None:
    vacancy = _make_vacancy()

    original_status = vacancy.status
    original_history = vacancy.history.copy()

    with pytest.raises(InvalidTransitionError):
        vacancy.change_status(
            VacancyStatus.OFFER,
            now=datetime(2026, 9, 2, 12, 0, tzinfo=UTC),
        )

    assert vacancy.status == original_status
    assert vacancy.history == original_history


def test_status_changes_are_added_to_history_in_order(
    vacancy: Vacancy,
) -> None:
    first_time = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
    second_time = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
    third_time = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)

    vacancy.change_status(
        VacancyStatus.JUDGED,
        now=first_time,
        reason="Passed initial check",
    )
    vacancy.change_status(
        VacancyStatus.SHORTLISTED,
        now=second_time,
        reason="Good match",
    )
    vacancy.change_status(
        VacancyStatus.APPLIED,
        now=third_time,
        reason="Application sent",
    )

    assert vacancy.status == VacancyStatus.APPLIED
    assert vacancy.history == [
        StatusChange(
            from_status=VacancyStatus.NEW,
            to_status=VacancyStatus.JUDGED,
            changed_at=first_time,
            reason="Passed initial check",
        ),
        StatusChange(
            from_status=VacancyStatus.JUDGED,
            to_status=VacancyStatus.SHORTLISTED,
            changed_at=second_time,
            reason="Good match",
        ),
        StatusChange(
            from_status=VacancyStatus.SHORTLISTED,
            to_status=VacancyStatus.APPLIED,
            changed_at=third_time,
            reason="Application sent",
        ),
    ]


def test_vacancies_do_not_share_history() -> None:
    first = _make_vacancy(external_id="1")
    second = _make_vacancy(external_id="2")

    first.change_status(
        VacancyStatus.JUDGED,
        now=datetime(2026, 9, 2, 12, 0, tzinfo=UTC),
    )

    assert len(first.history) == 1
    assert second.history == []
    assert first.history is not second.history


INVALID_VACANCIES: list[Callable[[], Vacancy]] = [
    lambda: _make_vacancy(external_id=""),
    lambda: _make_vacancy(title=""),
    lambda: _make_vacancy(title="   "),
    lambda: _make_vacancy(company=""),
    lambda: _make_vacancy(url="example.com/jobs/847958"),
    lambda: _make_vacancy(
        published_at=datetime(2026, 9, 1, 12, 0),
    ),
]

INVALID_VACANCY_IDS = [
    "empty-external-id",
    "empty-title",
    "whitespace-title",
    "empty-company",
    "url-without-scheme",
    "naive-published-at",
]


@pytest.mark.parametrize(
    "factory",
    INVALID_VACANCIES,
    ids=INVALID_VACANCY_IDS,
)
def test_invalid_vacancy_data_raises_error(
    factory: Callable[[], Vacancy],
) -> None:
    with pytest.raises(InvalidVacancyError):
        factory()


def test_naive_now_is_rejected(vacancy: Vacancy) -> None:
    naive_now = datetime(2026, 9, 2, 12, 0)

    with pytest.raises(InvalidVacancyError):
        vacancy.change_status(
            VacancyStatus.JUDGED,
            now=naive_now,
        )


def test_key(vacancy: Vacancy) -> None:
    assert vacancy.key == "djinni:847958"


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (
            PUBLISHED_AT,
            0,
        ),
        (
            PUBLISHED_AT + timedelta(days=45),
            45,
        ),
        (
            PUBLISHED_AT + timedelta(days=45, hours=23),
            45,
        ),
        (
            datetime(
                2026,
                10,
                16,
                7,
                0,
                tzinfo=timezone(timedelta(hours=-5)),
            ),
            45,
        ),
    ],
    ids=[
        "zero-days",
        "exactly-45-days",
        "45-days-plus-23-hours",
        "45-days-different-timezone",
    ],
)
def test_age_days(
    vacancy: Vacancy,
    now: datetime,
    expected: int,
) -> None:
    assert vacancy.age_days(now) == expected


ALLOWED_CASES = [
    (from_status, to_status)
    for from_status, to_statuses in ALLOWED_TRANSITIONS.items()
    for to_status in to_statuses
]

ALLOWED_CASE_IDS = [
    f"{from_status.value}-to-{to_status.value}" for from_status, to_status in ALLOWED_CASES
]


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    ALLOWED_CASES,
    ids=ALLOWED_CASE_IDS,
)
def test_allowed_transition_changes_vacancy(
    from_status: VacancyStatus,
    to_status: VacancyStatus,
) -> None:
    vacancy = _make_vacancy(status=from_status)
    now = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)

    vacancy.change_status(
        to_status,
        now=now,
        reason="test transition",
    )

    assert vacancy.status == to_status
    assert len(vacancy.history) == 1

    change = vacancy.history[0]

    assert change.from_status == from_status
    assert change.to_status == to_status
    assert change.changed_at == now
    assert change.reason == "test transition"
