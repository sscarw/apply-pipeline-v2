from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apply_pipeline.adapters.db.repositories.matches import SqlAlchemyMatchRepository
from apply_pipeline.adapters.db.repositories.profiles import SqlAlchemyProfileRepository
from apply_pipeline.adapters.db.repositories.users import SqlAlchemyUserRepository
from apply_pipeline.adapters.db.repositories.vacancies import SqlAlchemyVacancyRepository
from apply_pipeline.adapters.db.tables import MatchRow, MatchStatusChangeRow, UserRow, VacancyRow
from apply_pipeline.domain.errors import InvalidMatchError, NotFoundError
from apply_pipeline.domain.match import Match
from apply_pipeline.domain.scoring import MatchScore
from apply_pipeline.domain.transitions import MatchStatus
from apply_pipeline.domain.user import User

from .factories import CREATED_AT, AddVacancies, make_match, make_profile, make_user, reload

DAY_2 = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
DAY_3 = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


def _score(value: int) -> MatchScore:
    return MatchScore(value=value, blocked_by=(), scored_count=4, unknown_count=1)


async def _count(session: AsyncSession, table: type[MatchRow | MatchStatusChangeRow]) -> int:
    return await session.scalar(select(func.count()).select_from(table)) or 0


async def test_first_insert_returns_true(
    matches: SqlAlchemyMatchRepository,
    add_vacancies: AddVacancies,
    user: User,
) -> None:
    [key] = await add_vacancies("847958")

    assert await matches.add_if_absent(make_match(user.id, key)) is True


async def test_repeated_insert_does_not_duplicate(
    matches: SqlAlchemyMatchRepository,
    add_vacancies: AddVacancies,
    session: AsyncSession,
    user: User,
) -> None:
    [key] = await add_vacancies("847958")
    await matches.add_if_absent(make_match(user.id, key))

    assert await matches.add_if_absent(make_match(user.id, key)) is False
    assert await _count(session, MatchRow) == 1


async def test_same_vacancy_for_two_users_is_two_matches(
    matches: SqlAlchemyMatchRepository,
    users: SqlAlchemyUserRepository,
    add_vacancies: AddVacancies,
    user: User,
) -> None:
    other = make_user("olena@example.com")
    await users.add(other)
    [key] = await add_vacancies("847958")
    await matches.add_if_absent(make_match(user.id, key))

    assert await matches.add_if_absent(make_match(other.id, key)) is True


async def test_unknown_vacancy_raises_not_found(
    matches: SqlAlchemyMatchRepository,
    user: User,
) -> None:
    with pytest.raises(NotFoundError) as exc_info:
        await matches.add_if_absent(make_match(user.id, "djinni:does-not-exist"))

    assert (exc_info.value.entity, exc_info.value.key) == ("vacancy", "djinni:does-not-exist")


async def test_only_new_matches_can_be_added(
    matches: SqlAlchemyMatchRepository,
    add_vacancies: AddVacancies,
    user: User,
) -> None:
    [key] = await add_vacancies("847958")
    judged = make_match(user.id, key)
    judged.record_score(_score(80), profile_version=1, now=DAY_2)

    with pytest.raises(InvalidMatchError):
        await matches.add_if_absent(judged)


async def test_get_round_trip(
    matches: SqlAlchemyMatchRepository,
    add_vacancies: AddVacancies,
    session: AsyncSession,
    user: User,
) -> None:
    [key] = await add_vacancies("847958")
    match = make_match(user.id, key)
    await matches.add_if_absent(match)
    await reload(session)

    assert await matches.get(user.id, key) == match


async def test_get_missing_returns_none(
    matches: SqlAlchemyMatchRepository,
    add_vacancies: AddVacancies,
    user: User,
) -> None:
    [key] = await add_vacancies("847958")

    assert await matches.get(user.id, key) is None
    assert await matches.get(user.id, "djinni:does-not-exist") is None


async def test_other_users_match_is_invisible(
    matches: SqlAlchemyMatchRepository,
    users: SqlAlchemyUserRepository,
    add_vacancies: AddVacancies,
    user: User,
) -> None:
    other = make_user("olena@example.com")
    await users.add(other)
    [key] = await add_vacancies("847958")
    await matches.add_if_absent(make_match(other.id, key))

    assert await matches.get(user.id, key) is None


async def test_save_persists_status_score_and_history(
    matches: SqlAlchemyMatchRepository,
    add_vacancies: AddVacancies,
    session: AsyncSession,
    user: User,
) -> None:
    [key] = await add_vacancies("847958")
    await matches.add_if_absent(make_match(user.id, key))
    match = await matches.get(user.id, key)
    assert match is not None

    match.record_score(_score(79), profile_version=2, now=DAY_2)
    match.change_status(MatchStatus.SHORTLISTED, now=DAY_3, reason="looks good")
    await matches.save(match)
    await session.commit()
    await reload(session)

    assert await matches.get(user.id, key) == match
    assert await _count(session, MatchStatusChangeRow) == 2


async def test_saving_again_appends_only_new_history(
    matches: SqlAlchemyMatchRepository,
    add_vacancies: AddVacancies,
    session: AsyncSession,
    user: User,
) -> None:
    [key] = await add_vacancies("847958")
    await matches.add_if_absent(make_match(user.id, key))
    match = await matches.get(user.id, key)
    assert match is not None
    match.record_score(_score(79), profile_version=1, now=DAY_2)
    await matches.save(match)
    await reload(session)

    # A fresh copy from the database, as a later request would have.
    match = await matches.get(user.id, key)
    assert match is not None
    match.change_status(MatchStatus.SHORTLISTED, now=DAY_3)
    await matches.save(match)
    await matches.save(match)
    await reload(session)

    stored = await matches.get(user.id, key)
    assert stored is not None
    assert [change.to_status for change in stored.history] == [
        MatchStatus.JUDGED,
        MatchStatus.SHORTLISTED,
    ]
    assert await _count(session, MatchStatusChangeRow) == 2


async def test_save_unknown_match_raises_not_found(
    matches: SqlAlchemyMatchRepository,
    add_vacancies: AddVacancies,
    user: User,
) -> None:
    [key] = await add_vacancies("847958")

    for vacancy_key in (key, "djinni:does-not-exist"):
        with pytest.raises(NotFoundError) as exc_info:
            await matches.save(make_match(user.id, vacancy_key))

        assert exc_info.value.entity == "match"


async def _judged(
    matches: SqlAlchemyMatchRepository,
    user: User,
    key: str,
    score: int | None,
    *,
    created_at: datetime = CREATED_AT,
) -> None:
    await matches.add_if_absent(make_match(user.id, key, created_at=created_at))
    match = await matches.get(user.id, key)
    assert match is not None
    if score is None:
        match.change_status(MatchStatus.JUDGED, now=DAY_2)
    else:
        match.record_score(_score(score), profile_version=1, now=DAY_2)
    await matches.save(match)


def _values(found: list[Match]) -> list[int | None]:
    return [match.score.value if match.score else None for match in found]


async def test_list_puts_best_scores_first_and_unscored_last(
    matches: SqlAlchemyMatchRepository,
    add_vacancies: AddVacancies,
    session: AsyncSession,
    user: User,
) -> None:
    keys = await add_vacancies("1", "2", "3", "4")
    for key, score in zip(keys, [50, None, 90, 70], strict=True):
        await _judged(matches, user, key, score)
    await reload(session)

    found = await matches.list_for_user(user.id, status=MatchStatus.JUDGED, limit=10)

    assert _values(found) == [90, 70, 50, None]


async def test_list_breaks_ties_by_newest_first(
    matches: SqlAlchemyMatchRepository,
    add_vacancies: AddVacancies,
    session: AsyncSession,
    user: User,
) -> None:
    older, newer = await add_vacancies("1", "2")
    await _judged(matches, user, older, 80, created_at=CREATED_AT)
    await _judged(matches, user, newer, 80, created_at=CREATED_AT + timedelta(hours=1))
    await reload(session)

    found = await matches.list_for_user(user.id, status=MatchStatus.JUDGED, limit=10)

    assert [match.vacancy_key for match in found] == [newer, older]


async def test_list_respects_limit(
    matches: SqlAlchemyMatchRepository,
    add_vacancies: AddVacancies,
    user: User,
) -> None:
    keys = await add_vacancies("1", "2", "3")
    for key, score in zip(keys, [10, 30, 20], strict=True):
        await _judged(matches, user, key, score)

    found = await matches.list_for_user(user.id, status=MatchStatus.JUDGED, limit=2)

    assert _values(found) == [30, 20]


async def test_list_filters_by_status_and_user(
    matches: SqlAlchemyMatchRepository,
    users: SqlAlchemyUserRepository,
    add_vacancies: AddVacancies,
    user: User,
) -> None:
    other = make_user("olena@example.com")
    await users.add(other)
    judged_key, blocked_key, new_key = await add_vacancies("1", "2", "3")
    await _judged(matches, user, judged_key, 60)
    await _judged(matches, other, judged_key, 99)
    await matches.add_if_absent(make_match(user.id, new_key))
    await matches.add_if_absent(make_match(user.id, blocked_key))
    blocked = await matches.get(user.id, blocked_key)
    assert blocked is not None
    blocked.record_score(
        MatchScore(value=0, blocked_by=("no_crypto",), scored_count=1, unknown_count=0),
        profile_version=1,
        now=DAY_2,
    )
    await matches.save(blocked)

    judged = await matches.list_for_user(user.id, status=MatchStatus.JUDGED, limit=10)
    filtered = await matches.list_for_user(user.id, status=MatchStatus.FILTERED_OUT, limit=10)
    new = await matches.list_for_user(user.id, status=MatchStatus.NEW, limit=10)

    assert [match.vacancy_key for match in judged] == [judged_key]
    assert [match.vacancy_key for match in filtered] == [blocked_key]
    assert [match.vacancy_key for match in new] == [new_key]


async def test_deleting_user_removes_their_data_but_keeps_vacancies(
    matches: SqlAlchemyMatchRepository,
    profiles: SqlAlchemyProfileRepository,
    vacancies: SqlAlchemyVacancyRepository,
    add_vacancies: AddVacancies,
    session: AsyncSession,
    user: User,
) -> None:
    [key] = await add_vacancies("847958")
    await profiles.add(make_profile(user.id))
    await _judged(matches, user, key, 70)
    await reload(session)

    await session.execute(delete(UserRow).where(UserRow.id == user.id))
    await reload(session)

    assert await profiles.get_latest(user.id) is None
    assert await _count(session, MatchRow) == 0
    assert await _count(session, MatchStatusChangeRow) == 0
    assert await vacancies.get(key) is not None


async def test_deleting_vacancy_removes_its_matches(
    matches: SqlAlchemyMatchRepository,
    add_vacancies: AddVacancies,
    session: AsyncSession,
    user: User,
) -> None:
    [key] = await add_vacancies("847958")
    await _judged(matches, user, key, 70)
    await reload(session)

    await session.execute(delete(VacancyRow).where(VacancyRow.external_id == "847958"))
    await reload(session)

    assert await matches.get(user.id, key) is None
    assert await _count(session, MatchRow) == 0
    assert await _count(session, MatchStatusChangeRow) == 0
