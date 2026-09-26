from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from apply_pipeline.adapters.db.mappers import row_to_vacancy
from apply_pipeline.adapters.db.tables import VacancyRow
from apply_pipeline.domain.models import (
    Vacancy,
    split_vacancy_key,
)


class SqlAlchemyVacancyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_if_absent(self, vacancy: Vacancy) -> bool:
        statement = (
            insert(VacancyRow)
            .values(
                source=vacancy.source.value,
                external_id=vacancy.external_id,
                url=vacancy.url,
                title=vacancy.title,
                company=vacancy.company,
                description=vacancy.description,
                published_at=vacancy.published_at,
                location=vacancy.location,
                salary_text=vacancy.salary_text,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    VacancyRow.source,
                    VacancyRow.external_id,
                ]
            )
            .returning(VacancyRow.id)
        )

        inserted_id = await self._session.scalar(statement)

        return inserted_id is not None

    async def get(self, key: str) -> Vacancy | None:
        source, external_id = split_vacancy_key(key)

        statement = select(VacancyRow).where(
            VacancyRow.source == source.value,
            VacancyRow.external_id == external_id,
        )

        result = await self._session.execute(statement)
        row = result.scalar_one_or_none()

        if row is None:
            return None

        return row_to_vacancy(row)
