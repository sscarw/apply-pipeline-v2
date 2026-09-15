import pytest

from apply_pipeline.domain.transitions import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATUSES,
    VacancyStatus,
    can_transition,
)

EXPECTED_TRANSITIONS = {
    VacancyStatus.NEW: frozenset(
        {
            VacancyStatus.FILTERED_OUT,
            VacancyStatus.JUDGED,
        }
    ),
    VacancyStatus.FILTERED_OUT: frozenset(
        {
            VacancyStatus.SHORTLISTED,
        }
    ),
    VacancyStatus.JUDGED: frozenset(
        {
            VacancyStatus.SHORTLISTED,
            VacancyStatus.DISMISSED,
        }
    ),
    VacancyStatus.SHORTLISTED: frozenset(
        {
            VacancyStatus.APPLIED,
            VacancyStatus.DISMISSED,
        }
    ),
    VacancyStatus.DISMISSED: frozenset(
        {
            VacancyStatus.SHORTLISTED,
        }
    ),
    VacancyStatus.APPLIED: frozenset(
        {
            VacancyStatus.INTERVIEW,
            VacancyStatus.REJECTED,
        }
    ),
    VacancyStatus.INTERVIEW: frozenset(
        {
            VacancyStatus.OFFER,
            VacancyStatus.REJECTED,
        }
    ),
    VacancyStatus.OFFER: frozenset(),
    VacancyStatus.REJECTED: frozenset(),
}

ALLOWED_CASES = [
    (from_status, to_status)
    for from_status, to_statuses in ALLOWED_TRANSITIONS.items()
    for to_status in to_statuses
]


def test_transition_table_matches_business_rules() -> None:
    assert dict(ALLOWED_TRANSITIONS) == EXPECTED_TRANSITIONS


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    ALLOWED_CASES,
    ids=lambda status: status.value,
)
def test_can_transition_allows_configured_transitions(
    from_status: VacancyStatus,
    to_status: VacancyStatus,
) -> None:
    assert can_transition(from_status, to_status)


def test_every_status_exists_in_transition_table() -> None:
    assert set(ALLOWED_TRANSITIONS) == set(VacancyStatus)


def test_terminal_statuses() -> None:
    assert (
        frozenset(
            {
                VacancyStatus.OFFER,
                VacancyStatus.REJECTED,
            }
        )
        == TERMINAL_STATUSES
    )
