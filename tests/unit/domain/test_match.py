from datetime import UTC, datetime
from uuid import UUID

import pytest

from apply_pipeline.domain.errors import InvalidMatchError, InvalidTransitionError
from apply_pipeline.domain.match import Match, StatusChange
from apply_pipeline.domain.scoring import MatchScore
from apply_pipeline.domain.transitions import ALLOWED_TRANSITIONS, MatchStatus

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
CREATED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)

PASSING_SCORE = MatchScore(value=79, blocked_by=(), scored_count=5, unknown_count=1)
BLOCKED_SCORE = MatchScore(
    value=0,
    blocked_by=("python", "no_crypto"),
    scored_count=5,
    unknown_count=0,
)


def _make_match(
    *,
    status: MatchStatus = MatchStatus.NEW,
    vacancy_key: str = "djinni:847958",
    created_at: datetime = CREATED_AT,
) -> Match:
    return Match(
        user_id=USER_ID,
        vacancy_key=vacancy_key,
        created_at=created_at,
        status=status,
    )


@pytest.mark.parametrize(
    ("vacancy_key", "created_at"),
    [
        ("", CREATED_AT),
        ("   ", CREATED_AT),
        ("djinni-847958", CREATED_AT),
        ("linkedin:4362362525", CREATED_AT),
        ("djinni:", CREATED_AT),
        ("djinni:   ", CREATED_AT),
        ("djinni:847958", datetime(2026, 9, 1, 12, 0)),
    ],
    ids=[
        "empty-key",
        "whitespace-key",
        "key-without-colon",
        "unknown-source",
        "empty-external-id",
        "blank-external-id",
        "naive-created-at",
    ],
)
def test_invalid_match_raises_error(vacancy_key: str, created_at: datetime) -> None:
    with pytest.raises(InvalidMatchError):
        _make_match(vacancy_key=vacancy_key, created_at=created_at)


def test_new_match_starts_empty() -> None:
    match = _make_match()

    assert match.status == MatchStatus.NEW
    assert match.history == []
    assert match.score is None
    assert match.profile_version is None


ALLOWED_CASES = [
    (from_status, to_status)
    for from_status, to_statuses in ALLOWED_TRANSITIONS.items()
    for to_status in to_statuses
]


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    ALLOWED_CASES,
    ids=[f"{source.value}-to-{target.value}" for source, target in ALLOWED_CASES],
)
def test_allowed_transition_changes_match(
    from_status: MatchStatus,
    to_status: MatchStatus,
) -> None:
    match = _make_match(status=from_status)

    match.change_status(to_status, now=NOW, reason="test transition")

    assert match.status == to_status
    assert match.history == [
        StatusChange(
            from_status=from_status,
            to_status=to_status,
            changed_at=NOW,
            reason="test transition",
        )
    ]


FORBIDDEN_TRANSITIONS = [
    (MatchStatus.NEW, MatchStatus.OFFER),
    (MatchStatus.NEW, MatchStatus.NEW),
    (MatchStatus.OFFER, MatchStatus.SHORTLISTED),
    (MatchStatus.REJECTED, MatchStatus.APPLIED),
    (MatchStatus.APPLIED, MatchStatus.SHORTLISTED),
    (MatchStatus.JUDGED, MatchStatus.APPLIED),
]


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    FORBIDDEN_TRANSITIONS,
    ids=[f"{source.value}-to-{target.value}" for source, target in FORBIDDEN_TRANSITIONS],
)
def test_forbidden_transition_raises_error(
    from_status: MatchStatus,
    to_status: MatchStatus,
) -> None:
    match = _make_match(status=from_status)

    with pytest.raises(InvalidTransitionError) as exc_info:
        match.change_status(to_status, now=NOW)

    error = exc_info.value

    assert error.from_status == from_status
    assert error.to_status == to_status
    assert str(from_status) in str(error)
    assert str(to_status) in str(error)


def test_forbidden_transition_does_not_change_match() -> None:
    match = _make_match()

    with pytest.raises(InvalidTransitionError):
        match.change_status(MatchStatus.OFFER, now=NOW)

    assert match.status == MatchStatus.NEW
    assert match.history == []


def test_naive_now_is_rejected() -> None:
    match = _make_match()

    with pytest.raises(InvalidMatchError):
        match.change_status(MatchStatus.JUDGED, now=datetime(2026, 9, 2, 12, 0))

    assert match.status == MatchStatus.NEW
    assert match.history == []


def test_status_changes_are_added_to_history_in_order() -> None:
    match = _make_match()
    times = [datetime(2026, 9, day, 12, 0, tzinfo=UTC) for day in (2, 3, 4)]

    match.change_status(MatchStatus.JUDGED, now=times[0], reason="score 79")
    match.change_status(MatchStatus.SHORTLISTED, now=times[1], reason="Good match")
    match.change_status(MatchStatus.APPLIED, now=times[2], reason="Application sent")

    assert match.status == MatchStatus.APPLIED
    assert match.history == [
        StatusChange(MatchStatus.NEW, MatchStatus.JUDGED, times[0], "score 79"),
        StatusChange(MatchStatus.JUDGED, MatchStatus.SHORTLISTED, times[1], "Good match"),
        StatusChange(MatchStatus.SHORTLISTED, MatchStatus.APPLIED, times[2], "Application sent"),
    ]


def test_matches_do_not_share_history() -> None:
    first = _make_match(vacancy_key="djinni:1")
    second = _make_match(vacancy_key="djinni:2")

    first.change_status(MatchStatus.JUDGED, now=NOW)

    assert len(first.history) == 1
    assert second.history == []
    assert first.history is not second.history


def test_passing_score_moves_match_to_judged() -> None:
    match = _make_match()

    match.record_score(PASSING_SCORE, profile_version=3, now=NOW)

    assert match.status == MatchStatus.JUDGED
    assert match.score == PASSING_SCORE
    assert match.profile_version == 3
    assert match.history == [
        StatusChange(MatchStatus.NEW, MatchStatus.JUDGED, NOW, "score 79"),
    ]


def test_blocked_score_moves_match_to_filtered_out() -> None:
    match = _make_match()

    match.record_score(BLOCKED_SCORE, profile_version=1, now=NOW)

    assert match.status == MatchStatus.FILTERED_OUT
    assert match.score == BLOCKED_SCORE
    assert match.history[-1].reason == "blocked by: python, no_crypto"


def test_filtered_out_match_can_be_rescued() -> None:
    match = _make_match()
    match.record_score(BLOCKED_SCORE, profile_version=1, now=NOW)

    match.change_status(MatchStatus.SHORTLISTED, now=NOW, reason="rescued by user")

    assert match.status == MatchStatus.SHORTLISTED


def test_second_score_is_rejected_and_keeps_first() -> None:
    match = _make_match()
    match.record_score(PASSING_SCORE, profile_version=1, now=NOW)
    other_score = MatchScore(value=40, blocked_by=(), scored_count=5, unknown_count=0)

    with pytest.raises(InvalidTransitionError):
        match.record_score(other_score, profile_version=2, now=NOW)

    assert match.score == PASSING_SCORE
    assert match.profile_version == 1
    assert len(match.history) == 1


@pytest.mark.parametrize("profile_version", [0, -1])
def test_invalid_profile_version_is_rejected(profile_version: int) -> None:
    match = _make_match()

    with pytest.raises(InvalidMatchError):
        match.record_score(PASSING_SCORE, profile_version=profile_version, now=NOW)

    assert match.status == MatchStatus.NEW
    assert match.score is None


def test_score_with_naive_now_leaves_match_unchanged() -> None:
    match = _make_match()

    with pytest.raises(InvalidMatchError):
        match.record_score(PASSING_SCORE, profile_version=1, now=datetime(2026, 9, 2, 12, 0))

    assert match.status == MatchStatus.NEW
    assert match.score is None
    assert match.profile_version is None
