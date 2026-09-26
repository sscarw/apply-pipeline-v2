from uuid import UUID

from psycopg.errors import UniqueViolation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apply_pipeline.adapters.db.mappers import row_to_user, user_to_row
from apply_pipeline.adapters.db.tables import UserRow
from apply_pipeline.domain.errors import DuplicateEmailError
from apply_pipeline.domain.user import User, normalize_email

# Named by the naming convention in tables.py: uq_<table>_<columns>.
EMAIL_CONSTRAINT = "uq_users_email"


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> None:
        try:
            async with self._session.begin_nested():
                self._session.add(user_to_row(user))
        except IntegrityError as error:
            # Only the email constraint means "email taken"; a repeated primary key is a
            # bug in the caller and must not be reported as a busy email.
            if (
                isinstance(error.orig, UniqueViolation)
                and error.orig.diag.constraint_name == EMAIL_CONSTRAINT
            ):
                raise DuplicateEmailError(user.email) from error

            raise

    async def get(self, user_id: UUID) -> User | None:
        row = await self._session.get(UserRow, user_id)

        if row is None:
            return None

        return row_to_user(row)

    async def get_by_email(self, email: str) -> User | None:
        normalized_email = normalize_email(email)

        statement = select(UserRow).where(UserRow.email == normalized_email)

        result = await self._session.execute(statement)
        row = result.scalar_one_or_none()

        if row is None:
            return None

        return row_to_user(row)
