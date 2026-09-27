from datetime import UTC, datetime
from uuid import UUID

import pytest

from apply_pipeline.adapters.db.errors import CorruptedRowError
from apply_pipeline.adapters.db.mappers import apply_match_to_row, row_to_match
from apply_pipeline.adapters.db.tables import MatchRow, VacancyRow
from apply_pipeline.domain.match import Match, StatusChange
from apply_pipeline.domain.scoring import MatchScore
from apply_pipeline.domain.transitions import MatchStatus

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
CREATED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
DAY_2 = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
DAY_3 = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)

SCORE = MatchScore(value=79, blocked_by=(), scored_count=5, unknown_count=1)


def _vacancy_row(*, source: str = "djinni") -> VacancyRow:
    return VacancyRow(
        id=7,
        source=source,
        external_id="847958",
        url="https://djinni.co/jobs/847958/",
        title="Python Engineer",
        company="Broscorp",
        description="LLM agents in Python",
        published_at=CREATED_AT,
    )


def _new_row(*, source: str = "djinni") -> MatchRow:
    """A freshly inserted matches row, as add_if_absent leaves it."""
    return MatchRow(
        id=11,
        user_id=USER_ID,
        vacancy_id=7,
        vacancy=_vacancy_row(source=source),
        status="new",
        created_at=CREATED_AT,
    )


def _new_match() -> Match:
    return Match(user_id=USER_ID, vacancy_key="djinni:847958", created_at=CREATED_AT)


def test_new_row_becomes_new_match() -> None:
    assert row_to_match(_new_row()) == _new_match()


def test_vacancy_key_comes_from_joined_vacancy() -> None:
    assert row_to_match(_new_row()).vacancy_key == "djinni:847958"


def test_scored_match_round_trip() -> None:
    match = _new_match()
    match.record_score(SCORE, profile_version=2, now=DAY_2)
    match.change_status(MatchStatus.SHORTLISTED, now=DAY_3, reason="looks good")
    row = _new_row()

    apply_match_to_row(match, row)

    assert row_to_match(row) == match


def test_apply_writes_score_columns() -> None:
    match = _new_match()
    blocked = MatchScore(
        value=0, blocked_by=("no_crypto", "python"), scored_count=4, unknown_count=0
    )
    match.record_score(blocked, profile_version=5, now=DAY_2)
    row = _new_row()

    apply_match_to_row(match, row)

    assert row.status == "filtered_out"
    assert row.score_value == 0
    assert row.blocked_by == ["no_crypto", "python"]
    assert row.scored_count == 4
    assert row.unknown_count == 0
    assert row.profile_version == 5


def test_apply_without_score_clears_columns() -> None:
    scored = _new_match()
    scored.record_score(SCORE, profile_version=1, now=DAY_2)
    row = _new_row()
    apply_match_to_row(scored, row)

    apply_match_to_row(_new_match(), row)

    assert row.score_value is None
    assert row.blocked_by is None
    assert row.scored_count is None
    assert row.unknown_count is None
    assert row.profile_version is None


def test_apply_appends_only_new_history() -> None:
    match = _new_match()
    match.record_score(SCORE, profile_version=1, now=DAY_2)
    row = _new_row()
    apply_match_to_row(match, row)
    first_change_row = row.history[0]

    match.change_status(MatchStatus.SHORTLISTED, now=DAY_3, reason="looks good")
    apply_match_to_row(match, row)

    assert len(row.history) == 2
    # The saved row object is kept, not replaced: it already has a database id.
    assert row.history[0] is first_change_row
    assert (row.history[1].from_status, row.history[1].to_status) == ("judged", "shortlisted")
    assert row.history[1].changed_at == DAY_3
    assert row.history[1].reason == "looks good"


def test_apply_twice_without_changes_adds_nothing() -> None:
    match = _new_match()
    match.record_score(SCORE, profile_version=1, now=DAY_2)
    row = _new_row()

    apply_match_to_row(match, row)
    apply_match_to_row(match, row)

    assert len(row.history) == 1


def test_history_is_read_in_row_order() -> None:
    match = _new_match()
    match.record_score(SCORE, profile_version=1, now=DAY_2)
    match.change_status(MatchStatus.SHORTLISTED, now=DAY_3)
    row = _new_row()
    apply_match_to_row(match, row)

    assert row_to_match(row).history == [
        StatusChange(MatchStatus.NEW, MatchStatus.JUDGED, DAY_2, "score 79"),
        StatusChange(MatchStatus.JUDGED, MatchStatus.SHORTLISTED, DAY_3, None),
    ]


def test_unknown_status_raises() -> None:
    row = _new_row()
    row.status = "archived"

    with pytest.raises(CorruptedRowError) as exc_info:
        row_to_match(row)

    assert (exc_info.value.table, exc_info.value.row_id, exc_info.value.field) == (
        "matches",
        11,
        "status",
    )


def test_unknown_status_in_history_raises() -> None:
    match = _new_match()
    match.record_score(SCORE, profile_version=1, now=DAY_2)
    row = _new_row()
    apply_match_to_row(match, row)
    row.history[0].to_status = "archived"

    with pytest.raises(CorruptedRowError) as exc_info:
        row_to_match(row)

    assert exc_info.value.table == "match_status_changes"
    assert exc_info.value.field == "to_status"


def test_unknown_vacancy_source_raises() -> None:
    with pytest.raises(CorruptedRowError) as exc_info:
        row_to_match(_new_row(source="linkedin"))

    assert (exc_info.value.table, exc_info.value.row_id, exc_info.value.field) == (
        "vacancies",
        7,
        "source",
    )


@pytest.mark.parametrize(
    ("blocked_by", "scored_count", "unknown_count"),
    [
        (None, 5, 1),
        ([], None, 1),
        ([], 5, None),
    ],
    ids=["missing-blocked-by", "missing-scored-count", "missing-unknown-count"],
)
def test_partial_score_raises(
    blocked_by: list[str] | None,
    scored_count: int | None,
    unknown_count: int | None,
) -> None:
    row = _new_row()
    row.status = "judged"
    row.score_value = 79
    row.blocked_by, row.scored_count, row.unknown_count = blocked_by, scored_count, unknown_count

    with pytest.raises(CorruptedRowError) as exc_info:
        row_to_match(row)

    assert exc_info.value.field == "score"


@pytest.mark.parametrize(
    ("score_value", "blocked_by"),
    [(150, []), (40, ["python"])],
    ids=["value-over-100", "blocked-but-not-zero"],
)
def test_score_breaking_domain_rules_raises(score_value: int, blocked_by: list[str]) -> None:
    row = _new_row()
    row.status = "judged"
    row.score_value, row.blocked_by, row.scored_count, row.unknown_count = (
        score_value,
        blocked_by,
        5,
        0,
    )
    row.profile_version = 1

    with pytest.raises(CorruptedRowError) as exc_info:
        row_to_match(row)

    assert exc_info.value.field == "score"
    assert exc_info.value.value["value"] == score_value  # type: ignore[index]


def test_profile_version_without_score_raises() -> None:
    row = _new_row()
    row.profile_version = 3

    with pytest.raises(CorruptedRowError) as exc_info:
        row_to_match(row)

    assert exc_info.value.field == "score"


def test_score_without_profile_version_raises() -> None:
    row = _new_row()
    row.status = "judged"
    row.score_value, row.blocked_by, row.scored_count, row.unknown_count = 79, [], 5, 1

    with pytest.raises(CorruptedRowError) as exc_info:
        row_to_match(row)

    assert exc_info.value.value["profile_version"] is None  # type: ignore[index]


def test_leftover_blocked_by_without_score_raises() -> None:
    row = _new_row()
    row.blocked_by = ["python"]

    with pytest.raises(CorruptedRowError):
        row_to_match(row)
