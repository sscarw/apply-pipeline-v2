from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from apply_pipeline.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(str(settings.database_url))


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    async_session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return async_session_factory
