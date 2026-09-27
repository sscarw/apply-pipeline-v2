from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apply_pipeline.adapters.db.repositories.decisions import SqlAlchemyJudgeDecisionLog
from apply_pipeline.adapters.db.repositories.matches import SqlAlchemyMatchRepository
from apply_pipeline.adapters.db.repositories.users import SqlAlchemyUserRepository
from apply_pipeline.adapters.db.tables import JudgeDecisionRow, MatchRow, UserRow
from apply_pipeline.domain.errors import NotFoundError
from apply_pipeline.domain.judge import JudgeFailure
from apply_pipeline.domain.match import Match
from apply_pipeline.domain.ports import JudgeDecisionLog
from apply_pipeline.domain.user import User

from .factories import AddVacancies, make_match, make_user, make_verdict, reload

HASH = "a" * 64
DAY = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
UNAVAILABLE = JudgeFailure.UNAVAILABLE
INVALID_OUTPUT = JudgeFailure.INVALID_OUTPUT


@pytest.fixture
async def match(
    matches: SqlAlchemyMatchRepository,
    add_vacancies: AddVacancies,
    user: User,
) -> Match:
    [key] = await add_vacancies("847958")
    stored = make_match(user.id, key)
    await matches.add_if_absent(stored)
    return stored


async def _record(
    log: SqlAlchemyJudgeDecisionLog,
    match: Match,
    failure: JudgeFailure | None = None,
    *,
    cost: Decimal | None = Decimal("0.0017"),
    decided_at: datetime = DAY,
    profile_version: int = 1,
    vacancy_hash: str = HASH,
) -> None:
    await log.record(
        match,
        make_verdict(failure, cost=cost),
        profile_version=profile_version,
        vacancy_hash=vacancy_hash,
        decided_at=decided_at,
    )


async def _attempted(log: SqlAlchemyJudgeDecisionLog, match: Match, **key: Any) -> bool:
    values: dict[str, Any] = {
        "profile_version": 1,
        "prompt_version": "judge_v2",
        "vacancy_hash": HASH,
        **key,
    }
    return await log.was_attempted(match, **values)


async def _count(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(JudgeDecisionRow)) or 0


async def test_log_satisfies_port(decisions: SqlAlchemyJudgeDecisionLog) -> None:
    log: JudgeDecisionLog = decisions

    assert log is decisions


async def test_record_stores_the_decision(
    decisions: SqlAlchemyJudgeDecisionLog,
    session: AsyncSession,
    match: Match,
) -> None:
    await _record(decisions, match, profile_version=3)
    await reload(session)

    row = await session.scalar(select(JudgeDecisionRow))

    assert row is not None
    assert (row.profile_version, row.prompt_version, row.vacancy_hash) == (3, "judge_v2", HASH)
    assert row.failure is None
    assert row.results[0]["status"] == "met"
    assert row.cost_usd == Decimal("0.001700")
    assert row.decided_at == DAY


async def test_every_failure_is_stored(
    decisions: SqlAlchemyJudgeDecisionLog,
    session: AsyncSession,
    match: Match,
) -> None:
    await _record(decisions, match, UNAVAILABLE)
    await _record(decisions, match, INVALID_OUTPUT)
    await reload(session)

    failures = (await session.scalars(select(JudgeDecisionRow.failure))).all()

    assert set(failures) == {"invalid_output", "unavailable"}


async def test_record_for_unknown_match_raises(
    decisions: SqlAlchemyJudgeDecisionLog,
    add_vacancies: AddVacancies,
    user: User,
) -> None:
    [key] = await add_vacancies("847958")

    with pytest.raises(NotFoundError) as exc_info:
        await _record(decisions, make_match(user.id, key))

    assert exc_info.value.entity == "match"


async def test_nothing_attempted_yet(decisions: SqlAlchemyJudgeDecisionLog, match: Match) -> None:
    assert await _attempted(decisions, match) is False


async def test_success_counts_as_attempted(
    decisions: SqlAlchemyJudgeDecisionLog,
    match: Match,
) -> None:
    # The success row has failure = NULL. A plain `failure != 'unavailable'` filter
    # would drop it, because NULL != 'x' is NULL in SQL, not TRUE.
    await _record(decisions, match)

    assert await _attempted(decisions, match) is True


async def test_paid_failure_counts_as_attempted(
    decisions: SqlAlchemyJudgeDecisionLog,
    match: Match,
) -> None:
    await _record(decisions, match, INVALID_OUTPUT)

    assert await _attempted(decisions, match) is True


async def test_free_failure_is_retried(decisions: SqlAlchemyJudgeDecisionLog, match: Match) -> None:
    await _record(decisions, match, UNAVAILABLE)
    await _record(decisions, match, UNAVAILABLE)

    assert await _attempted(decisions, match) is False


@pytest.mark.parametrize(
    "other_key",
    [
        {"profile_version": 2},
        {"prompt_version": "judge_v3"},
        {"vacancy_hash": "b" * 64},
    ],
    ids=["new-profile-version", "new-prompt-version", "vacancy-text-changed"],
)
async def test_any_changed_key_part_means_judge_again(
    decisions: SqlAlchemyJudgeDecisionLog,
    match: Match,
    other_key: dict[str, Any],
) -> None:
    await _record(decisions, match)

    assert await _attempted(decisions, match, **other_key) is False


async def test_other_users_decisions_do_not_count(
    decisions: SqlAlchemyJudgeDecisionLog,
    matches: SqlAlchemyMatchRepository,
    users: SqlAlchemyUserRepository,
    match: Match,
) -> None:
    other = make_user("olena@example.com")
    await users.add(other)
    other_match = make_match(other.id, match.vacancy_key)
    await matches.add_if_absent(other_match)
    await _record(decisions, other_match)

    assert await _attempted(decisions, match) is False


async def test_unknown_match_was_never_attempted(
    decisions: SqlAlchemyJudgeDecisionLog,
    add_vacancies: AddVacancies,
    user: User,
) -> None:
    [key] = await add_vacancies("847958")

    assert await _attempted(decisions, make_match(user.id, key)) is False


async def test_second_success_for_the_same_key_is_rejected(
    decisions: SqlAlchemyJudgeDecisionLog,
    session: AsyncSession,
    match: Match,
) -> None:
    await _record(decisions, match)
    await session.flush()

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await _record(decisions, match)

    assert await _count(session) == 1


async def test_failures_and_manual_rejudge_are_allowed(
    decisions: SqlAlchemyJudgeDecisionLog,
    session: AsyncSession,
    match: Match,
) -> None:
    # Two paid failures, then a manual re-judge that succeeds: all three are real events.
    await _record(decisions, match, INVALID_OUTPUT)
    await _record(decisions, match, INVALID_OUTPUT)
    await _record(decisions, match)
    await session.flush()

    assert await _count(session) == 3


async def test_spent_sums_costs_from_the_given_moment(
    decisions: SqlAlchemyJudgeDecisionLog,
    match: Match,
    user: User,
) -> None:
    # Two successes need different keys: the unique index allows one success per key.
    await _record(
        decisions,
        match,
        cost=Decimal("0.5"),
        decided_at=DAY - timedelta(days=1),
        profile_version=1,
    )
    await _record(decisions, match, INVALID_OUTPUT, cost=Decimal("0.2"), decided_at=DAY)
    await _record(
        decisions,
        match,
        cost=Decimal("0.03"),
        decided_at=DAY + timedelta(hours=1),
        profile_version=2,
    )

    spent = await decisions.spent_since(user.id, since=DAY)

    # The decision exactly at `since` is included, the one a day earlier is not.
    assert spent == Decimal("0.23")
    assert isinstance(spent, Decimal)


async def test_free_and_unpriced_decisions_cost_nothing(
    decisions: SqlAlchemyJudgeDecisionLog,
    match: Match,
    user: User,
) -> None:
    await _record(decisions, match, UNAVAILABLE)
    await _record(decisions, match, cost=None)
    await _record(decisions, match, INVALID_OUTPUT, cost=Decimal("0.01"))

    assert await decisions.spent_since(user.id, since=DAY) == Decimal("0.01")


async def test_nothing_spent_is_zero_not_none(
    decisions: SqlAlchemyJudgeDecisionLog,
    user: User,
) -> None:
    spent = await decisions.spent_since(user.id, since=DAY)

    assert spent == Decimal("0")
    assert isinstance(spent, Decimal)


async def test_spending_is_per_user(
    decisions: SqlAlchemyJudgeDecisionLog,
    matches: SqlAlchemyMatchRepository,
    users: SqlAlchemyUserRepository,
    match: Match,
    user: User,
) -> None:
    other = make_user("olena@example.com")
    await users.add(other)
    other_match = make_match(other.id, match.vacancy_key)
    await matches.add_if_absent(other_match)
    await _record(decisions, match, cost=Decimal("0.1"))
    await _record(decisions, other_match, cost=Decimal("0.9"))

    assert await decisions.spent_since(user.id, since=DAY) == Decimal("0.1")
    assert await decisions.spent_since(other.id, since=DAY) == Decimal("0.9")


async def test_deleting_match_deletes_its_decisions(
    decisions: SqlAlchemyJudgeDecisionLog,
    session: AsyncSession,
    match: Match,
) -> None:
    await _record(decisions, match)
    await reload(session)

    await session.execute(delete(MatchRow))

    assert await _count(session) == 0


async def test_deleting_user_deletes_their_decisions(
    decisions: SqlAlchemyJudgeDecisionLog,
    session: AsyncSession,
    match: Match,
    user: User,
) -> None:
    await _record(decisions, match)
    await reload(session)

    await session.execute(delete(UserRow).where(UserRow.id == user.id))

    assert await _count(session) == 0
