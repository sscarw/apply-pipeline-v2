"""Repository fixtures shared by the repository integration tests."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apply_pipeline.adapters.db.repositories.decisions import SqlAlchemyJudgeDecisionLog
from apply_pipeline.adapters.db.repositories.matches import SqlAlchemyMatchRepository
from apply_pipeline.adapters.db.repositories.profiles import SqlAlchemyProfileRepository
from apply_pipeline.adapters.db.repositories.users import SqlAlchemyUserRepository
from apply_pipeline.adapters.db.repositories.vacancies import SqlAlchemyVacancyRepository
from apply_pipeline.domain.user import User

from .factories import AddVacancies, make_user, make_vacancy


@pytest.fixture
def vacancies(session: AsyncSession) -> SqlAlchemyVacancyRepository:
    return SqlAlchemyVacancyRepository(session)


@pytest.fixture
def users(session: AsyncSession) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(session)


@pytest.fixture
def profiles(session: AsyncSession) -> SqlAlchemyProfileRepository:
    return SqlAlchemyProfileRepository(session)


@pytest.fixture
def matches(session: AsyncSession) -> SqlAlchemyMatchRepository:
    return SqlAlchemyMatchRepository(session)


@pytest.fixture
def decisions(session: AsyncSession) -> SqlAlchemyJudgeDecisionLog:
    return SqlAlchemyJudgeDecisionLog(session)


@pytest.fixture
async def user(users: SqlAlchemyUserRepository) -> User:
    user = make_user()
    await users.add(user)
    return user


@pytest.fixture
def add_vacancies(vacancies: SqlAlchemyVacancyRepository) -> AddVacancies:
    """Store vacancies with the given external ids and return their keys."""

    async def add(*external_ids: str) -> list[str]:
        keys = []
        for external_id in external_ids:
            vacancy = make_vacancy(external_id)
            await vacancies.add_if_absent(vacancy)
            keys.append(vacancy.key)
        return keys

    return add
