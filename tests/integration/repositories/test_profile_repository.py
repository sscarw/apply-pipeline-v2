from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apply_pipeline.adapters.db.repositories.profiles import SqlAlchemyProfileRepository
from apply_pipeline.adapters.db.repositories.users import SqlAlchemyUserRepository
from apply_pipeline.domain.errors import NotFoundError, ProfileVersionConflictError
from apply_pipeline.domain.profile import Currency, Salary, WorkFormat
from apply_pipeline.domain.user import User

from .factories import make_profile, make_user, reload

LATER = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)


async def test_round_trip(
    profiles: SqlAlchemyProfileRepository,
    session: AsyncSession,
    user: User,
) -> None:
    profile = make_profile(
        user.id,
        work_formats=frozenset({WorkFormat.REMOTE, WorkFormat.HYBRID}),
        city="Львів",
        min_salary=Salary(500, Currency.USD),
    )
    await profiles.add(profile)
    await reload(session)

    assert await profiles.get(user.id, 1) == profile


async def test_latest_version_wins(
    profiles: SqlAlchemyProfileRepository,
    session: AsyncSession,
    user: User,
) -> None:
    first = make_profile(user.id)
    second = first.revise(now=LATER, desired_roles=("AI Engineer",))
    third = second.revise(now=LATER, experience_years=1)
    # Stored out of order on purpose: "latest" means the highest version, not the last insert.
    for profile in (first, third, second):
        await profiles.add(profile)
    await reload(session)

    assert await profiles.get_latest(user.id) == third
    assert await profiles.get(user.id, 1) == first
    assert await profiles.get(user.id, 2) == second


async def test_missing_profiles_return_none(
    profiles: SqlAlchemyProfileRepository,
    user: User,
) -> None:
    assert await profiles.get_latest(user.id) is None
    assert await profiles.get(user.id, 1) is None


async def test_profiles_of_other_users_are_invisible(
    profiles: SqlAlchemyProfileRepository,
    users: SqlAlchemyUserRepository,
    user: User,
) -> None:
    other = make_user("olena@example.com")
    await users.add(other)
    await profiles.add(make_profile(other.id))

    assert await profiles.get_latest(user.id) is None


async def test_same_version_twice_is_a_conflict(
    profiles: SqlAlchemyProfileRepository,
    session: AsyncSession,
    user: User,
) -> None:
    original = make_profile(user.id)
    await profiles.add(original)
    competing = make_profile(user.id, desired_roles=("Data Engineer",))

    with pytest.raises(ProfileVersionConflictError) as exc_info:
        await profiles.add(competing)

    assert (exc_info.value.user_id, exc_info.value.version) == (user.id, 1)
    # The loser's edit is not stored, and the transaction is still usable.
    await reload(session)
    assert await profiles.get_latest(user.id) == original


async def test_unknown_user_raises_not_found(profiles: SqlAlchemyProfileRepository) -> None:
    missing_user_id = uuid4()

    with pytest.raises(NotFoundError) as exc_info:
        await profiles.add(make_profile(missing_user_id))

    assert exc_info.value.entity == "user"
    assert exc_info.value.key == str(missing_user_id)
