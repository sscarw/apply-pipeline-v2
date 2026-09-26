import pytest

from apply_pipeline.domain.transitions import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATUSES,
    MatchStatus,
    can_transition,
)

EXPECTED_TRANSITIONS = {
    MatchStatus.NEW: frozenset(
        {
            MatchStatus.FILTERED_OUT,
            MatchStatus.JUDGED,
        }
    ),
    MatchStatus.FILTERED_OUT: frozenset(
        {
            MatchStatus.SHORTLISTED,
        }
    ),
    MatchStatus.JUDGED: frozenset(
        {
            MatchStatus.SHORTLISTED,
            MatchStatus.DISMISSED,
        }
    ),
    MatchStatus.SHORTLISTED: frozenset(
        {
            MatchStatus.APPLIED,
            MatchStatus.DISMISSED,
        }
    ),
    MatchStatus.DISMISSED: frozenset(
        {
            MatchStatus.SHORTLISTED,
        }
    ),
    MatchStatus.APPLIED: frozenset(
        {
            MatchStatus.INTERVIEW,
            MatchStatus.REJECTED,
        }
    ),
    MatchStatus.INTERVIEW: frozenset(
        {
            MatchStatus.OFFER,
            MatchStatus.REJECTED,
        }
    ),
    MatchStatus.OFFER: frozenset(),
    MatchStatus.REJECTED: frozenset(),
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
    from_status: MatchStatus,
    to_status: MatchStatus,
) -> None:
    assert can_transition(from_status, to_status)


def test_every_status_exists_in_transition_table() -> None:
    assert set(ALLOWED_TRANSITIONS) == set(MatchStatus)


def test_terminal_statuses() -> None:
    assert (
        frozenset(
            {
                MatchStatus.OFFER,
                MatchStatus.REJECTED,
            }
        )
        == TERMINAL_STATUSES
    )
