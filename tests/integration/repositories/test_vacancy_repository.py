import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apply_pipeline.adapters.db.repositories.vacancies import SqlAlchemyVacancyRepository
from apply_pipeline.adapters.db.tables import VacancyRow
from apply_pipeline.domain.errors import InvalidVacancyError
from apply_pipeline.domain.transitions import Source

from .factories import make_vacancy, reload


async def _count(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(VacancyRow)) or 0


async def test_first_insert_returns_true(vacancies: SqlAlchemyVacancyRepository) -> None:
    assert await vacancies.add_if_absent(make_vacancy()) is True


async def test_repeated_insert_does_not_duplicate(
    vacancies: SqlAlchemyVacancyRepository,
    session: AsyncSession,
) -> None:
    await vacancies.add_if_absent(make_vacancy())

    assert await vacancies.add_if_absent(make_vacancy()) is False
    assert await _count(session) == 1


async def test_repeated_insert_keeps_first_version(
    vacancies: SqlAlchemyVacancyRepository,
    session: AsyncSession,
) -> None:
    await vacancies.add_if_absent(make_vacancy(title="First title"))
    await vacancies.add_if_absent(make_vacancy(title="Changed title"))
    await reload(session)

    stored = await vacancies.get("djinni:847958")

    assert stored is not None
    assert stored.title == "First title"


async def test_same_external_id_from_other_source_is_another_vacancy(
    vacancies: SqlAlchemyVacancyRepository,
) -> None:
    await vacancies.add_if_absent(make_vacancy())

    assert await vacancies.add_if_absent(make_vacancy(source=Source.DOU)) is True


async def test_get_round_trip(
    vacancies: SqlAlchemyVacancyRepository,
    session: AsyncSession,
) -> None:
    vacancy = make_vacancy(location=None, salary_text=None)
    await vacancies.add_if_absent(vacancy)
    await reload(session)

    assert await vacancies.get(vacancy.key) == vacancy


async def test_get_unknown_returns_none(vacancies: SqlAlchemyVacancyRepository) -> None:
    assert await vacancies.get("djinni:does-not-exist") is None


async def test_get_invalid_key_raises(vacancies: SqlAlchemyVacancyRepository) -> None:
    with pytest.raises(InvalidVacancyError):
        await vacancies.get("linkedin:1")
