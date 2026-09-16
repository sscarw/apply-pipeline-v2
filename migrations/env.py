"""Alembic environment: runs migrations against the database from the app settings."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from apply_pipeline.adapters.db import tables
from apply_pipeline.config import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The URL comes from the app settings, never from alembic.ini, so the password stays
# out of git. Alembic's config is a configparser, where "%" starts an interpolation.
database_url = str(get_settings().database_url)
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

# Importing the tables module registers every table on Base.metadata,
# which is what autogenerate compares against the database.
target_metadata = tables.Base.metadata


def run_migrations_offline() -> None:
    """Emit the migration SQL to stdout instead of running it (alembic upgrade --sql)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    # Async psycopg cannot run on the ProactorEventLoop that Windows uses by default,
    # so the selector loop is used on every platform.
    asyncio.run(run_async_migrations(), loop_factory=asyncio.SelectorEventLoop)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
