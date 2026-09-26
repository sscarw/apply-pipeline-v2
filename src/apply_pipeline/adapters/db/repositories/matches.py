from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from apply_pipeline.adapters.db.mappers import (
    apply_match_to_row,
    row_to_match,
)
from apply_pipeline.adapters.db.tables import MatchRow, VacancyRow
from apply_pipeline.domain.errors import InvalidMatchError, NotFoundError
from apply_pipeline.domain.match import Match
from apply_pipeline.domain.models import split_vacancy_key
from apply_pipeline.domain.transitions import MatchStatus


class SqlAlchemyMatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _vacancy_id(self, key: str) -> int | None:
        source, external_id = split_vacancy_key(key)

        statement = select(VacancyRow.id).where(
            VacancyRow.source == source.value,
            VacancyRow.external_id == external_id,
        )

        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def _load(
        self,
        user_id: UUID,
        vacancy_id: int,
    ) -> MatchRow | None:
        statement = (
            select(MatchRow)
            .where(
                MatchRow.user_id == user_id,
                MatchRow.vacancy_id == vacancy_id,
            )
            .options(
                joinedload(MatchRow.vacancy),
                selectinload(MatchRow.history),
            )
        )

        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def add_if_absent(self, match: Match) -> bool:
        if match.status != MatchStatus.NEW or match.history or match.score is not None:
            raise InvalidMatchError("Only a new match without history or score can be added.")

        vacancy_id = await self._vacancy_id(match.vacancy_key)

        if vacancy_id is None:
            raise NotFoundError(
                "vacancy",
                match.vacancy_key,
            )

        statement = (
            insert(MatchRow)
            .values(
                user_id=match.user_id,
                vacancy_id=vacancy_id,
                status=match.status.value,
                created_at=match.created_at,
                profile_version=match.profile_version,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    MatchRow.user_id,
                    MatchRow.vacancy_id,
                ]
            )
            .returning(MatchRow.id)
        )

        inserted_id = await self._session.scalar(statement)

        return inserted_id is not None

    async def get(
        self,
        user_id: UUID,
        vacancy_key: str,
    ) -> Match | None:
        vacancy_id = await self._vacancy_id(vacancy_key)

        if vacancy_id is None:
            return None

        row = await self._load(
            user_id,
            vacancy_id,
        )

        if row is None:
            return None

        return row_to_match(row)

    async def save(self, match: Match) -> None:
        match_key = f"{match.user_id} / {match.vacancy_key}"

        vacancy_id = await self._vacancy_id(match.vacancy_key)

        if vacancy_id is None:
            raise NotFoundError(
                "match",
                match_key,
            )

        row = await self._load(
            match.user_id,
            vacancy_id,
        )

        if row is None:
            raise NotFoundError(
                "match",
                match_key,
            )

        apply_match_to_row(
            match,
            row,
        )

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        status: MatchStatus,
        limit: int,
    ) -> list[Match]:
        statement = (
            select(MatchRow)
            .where(
                MatchRow.user_id == user_id,
                MatchRow.status == status.value,
            )
            .order_by(
                MatchRow.score_value.desc().nulls_last(),
                MatchRow.created_at.desc(),
            )
            .limit(limit)
            .options(
                joinedload(MatchRow.vacancy),
                selectinload(MatchRow.history),
            )
        )

        result = await self._session.execute(statement)
        rows = result.scalars().all()

        return [row_to_match(row) for row in rows]
