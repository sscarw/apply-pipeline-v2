from uuid import UUID

from psycopg.errors import ForeignKeyViolation, UniqueViolation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apply_pipeline.adapters.db.mappers import (
    profile_to_row,
    row_to_profile,
)
from apply_pipeline.adapters.db.tables import CandidateProfileRow
from apply_pipeline.domain.errors import (
    NotFoundError,
    ProfileVersionConflictError,
)
from apply_pipeline.domain.profile import CandidateProfile


class SqlAlchemyProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, profile: CandidateProfile) -> None:
        try:
            async with self._session.begin_nested():
                self._session.add(profile_to_row(profile))

        except IntegrityError as error:
            if isinstance(error.orig, UniqueViolation):
                raise ProfileVersionConflictError(
                    profile.user_id,
                    profile.version,
                ) from error

            if isinstance(error.orig, ForeignKeyViolation):
                raise NotFoundError(
                    "user",
                    str(profile.user_id),
                ) from error

            raise

    async def get_latest(
        self,
        user_id: UUID,
    ) -> CandidateProfile | None:
        statement = (
            select(CandidateProfileRow)
            .where(CandidateProfileRow.user_id == user_id)
            .order_by(CandidateProfileRow.version.desc())
            .limit(1)
        )

        result = await self._session.execute(statement)
        row = result.scalar_one_or_none()

        if row is None:
            return None

        return row_to_profile(row)

    async def get(
        self,
        user_id: UUID,
        version: int,
    ) -> CandidateProfile | None:
        statement = select(CandidateProfileRow).where(
            CandidateProfileRow.user_id == user_id,
            CandidateProfileRow.version == version,
        )

        result = await self._session.execute(statement)
        row = result.scalar_one_or_none()

        if row is None:
            return None

        return row_to_profile(row)
