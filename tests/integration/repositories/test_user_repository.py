from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apply_pipeline.adapters.db.repositories.users import SqlAlchemyUserRepository
from apply_pipeline.domain.errors import DuplicateEmailError
from apply_pipeline.domain.user import Language

from .factories import make_user, reload


async def test_round_trip(users: SqlAlchemyUserRepository, session: AsyncSession) -> None:
    user = make_user(language=Language.EN, monthly_budget_usd=Decimal("2.50"), is_active=False)
    await users.add(user)
    await reload(session)

    assert await users.get(user.id) == user


async def test_get_unknown_returns_none(users: SqlAlchemyUserRepository) -> None:
    assert await users.get(make_user().id) is None


@pytest.mark.parametrize(
    "lookup",
    ["andrii@example.com", "Andrii@Example.COM", "  andrii@example.com "],
    ids=["exact", "other-case", "surrounding-spaces"],
)
async def test_get_by_email_normalizes_input(
    users: SqlAlchemyUserRepository,
    session: AsyncSession,
    lookup: str,
) -> None:
    user = make_user("andrii@example.com")
    await users.add(user)
    await reload(session)

    found = await users.get_by_email(lookup)

    assert found is not None
    assert found.id == user.id


async def test_get_by_unknown_email_returns_none(users: SqlAlchemyUserRepository) -> None:
    assert await users.get_by_email("nobody@example.com") is None


async def test_duplicate_email_raises_domain_error(users: SqlAlchemyUserRepository) -> None:
    await users.add(make_user("andrii@example.com"))

    with pytest.raises(DuplicateEmailError) as exc_info:
        await users.add(make_user("ANDRII@example.com"))

    assert exc_info.value.email == "andrii@example.com"
    assert isinstance(exc_info.value.__cause__, IntegrityError)


async def test_transaction_survives_duplicate_email(
    users: SqlAlchemyUserRepository,
    session: AsyncSession,
) -> None:
    first = make_user("andrii@example.com")
    await users.add(first)

    with pytest.raises(DuplicateEmailError):
        await users.add(make_user("andrii@example.com"))

    # Only the savepoint was rolled back: the session keeps working and keeps earlier rows.
    second = make_user("olena@example.com")
    await users.add(second)
    await session.commit()
    await reload(session)

    assert await users.get(first.id) == first
    assert await users.get(second.id) == second


async def test_repeated_id_is_not_reported_as_busy_email(
    users: SqlAlchemyUserRepository,
) -> None:
    user = make_user("andrii@example.com")
    await users.add(user)
    same_id = make_user("other@example.com", id=user.id)

    with pytest.raises(IntegrityError):
        await users.add(same_id)
