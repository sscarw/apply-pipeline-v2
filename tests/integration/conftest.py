"""Fixtures for integration tests: a disposable PostgreSQL with the real schema.

One container is started for the whole test run and migrated with Alembic, exactly
as production is. Every test then gets a session inside a transaction that is rolled
back afterwards, so tests never see each other's rows.
"""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from docker.errors import DockerException
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from testcontainers.community.postgres import PostgresContainer

from apply_pipeline.adapters.db.engine import create_engine
from apply_pipeline.config import Settings, get_settings

# Same image as docker-compose.yml, so tests run against the same PostgreSQL and pgvector.
POSTGRES_IMAGE = "pgvector/pgvector:pg17"
# Settings require a Redis URL; database tests never connect to it.
UNUSED_REDIS_URL = "redis://127.0.0.1:6379/0"

INTEGRATION_DIR = Path(__file__).parent
PROJECT_ROOT = INTEGRATION_DIR.parents[1]


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark every test in this folder, so `pytest -m "not integration"` skips them."""
    for item in items:
        if item.path.is_relative_to(INTEGRATION_DIR):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """Start PostgreSQL in Docker and return its URL with the psycopg driver."""
    container = PostgresContainer(POSTGRES_IMAGE, driver="psycopg")
    try:
        container.start()
    except DockerException as error:
        pytest.skip(f"Docker is not available, integration tests skipped: {error}")

    try:
        host = container.get_container_host_ip()
        # On Windows "localhost" resolves to ::1 first, and psycopg can hang on it.
        if host == "localhost":
            host = "127.0.0.1"
        yield container.get_connection_url(host=host)
    finally:
        container.stop()


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    return Config(str(PROJECT_ROOT / "alembic.ini"))


@pytest.fixture(scope="session")
def migrated_database_url(postgres_url: str, alembic_config: Config) -> str:
    """Apply all Alembic migrations to the test database and return its URL."""
    # migrations/env.py reads the URL from get_settings(), so point the settings at the
    # container for the duration of the upgrade and drop the cached settings around it.
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DATABASE_URL", postgres_url)
        patch.setenv("REDIS_URL", UNUSED_REDIS_URL)
        get_settings.cache_clear()
        command.upgrade(alembic_config, "head")
    get_settings.cache_clear()
    return postgres_url


@pytest.fixture(scope="session")
def test_settings(migrated_database_url: str) -> Settings:
    return Settings(database_url=migrated_database_url, redis_url=UNUSED_REDIS_URL)


@pytest.fixture(scope="session")
async def engine(test_settings: Settings) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(test_settings)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session whose changes are rolled back after the test, even if it commits.

    The session joins an outer transaction; its own commit() only releases a savepoint,
    and the outer transaction is rolled back at the end.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
