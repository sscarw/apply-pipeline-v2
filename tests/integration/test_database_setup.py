"""Checks that the integration test infrastructure itself works."""

from datetime import UTC, datetime

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, inspect, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from apply_pipeline.adapters.db.mappers import vacancy_to_row
from apply_pipeline.adapters.db.tables import VacancyRow
from apply_pipeline.domain.models import Vacancy
from apply_pipeline.domain.transitions import Source


def _table_names(connection: Connection) -> list[str]:
    return inspect(connection).get_table_names()


async def test_database_is_migrated_to_head(
    engine: AsyncEngine,
    alembic_config: Config,
) -> None:
    expected_head = ScriptDirectory.from_config(alembic_config).get_current_head()

    async with engine.connect() as connection:
        current = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        tables = await connection.run_sync(_table_names)

    assert current == expected_head
    assert {"vacancies", "vacancy_status_changes"} <= set(tables)


async def test_committed_rows_are_rolled_back_after_the_test(
    session: AsyncSession,
    engine: AsyncEngine,
) -> None:
    vacancy = Vacancy(
        source=Source.DJINNI,
        external_id="infra-check",
        url="https://example.com/jobs/infra-check",
        title="Infrastructure check",
        company="Test",
        description="Row that must not outlive the test",
        published_at=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
    )
    session.add(vacancy_to_row(vacancy))
    await session.commit()

    in_session = await session.scalar(select(func.count()).select_from(VacancyRow))

    # A separate connection sees only committed data outside the test's transaction.
    async with engine.connect() as other_connection:
        outside = await other_connection.scalar(select(func.count()).select_from(VacancyRow))

    assert in_session == 1
    assert outside == 0
