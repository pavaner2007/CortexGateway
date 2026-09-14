"""
Alembic Migration Environment — Cortex Gateway.

Configures async SQLAlchemy migrations using the same database URL
as the application (from app.config.settings).

Supports both:
- Offline mode (generates SQL without connecting)
- Online mode  (runs migrations against the live database)
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import the shared declarative base — Alembic inspects Base.metadata
# to discover all tables defined in ORM models.
from app.database.base import Base

# Import all ORM models so their tables register with Base.metadata.
# Alembic will not see tables that are not imported here.
import app.auth.models  # noqa: F401

# Alembic Config object provides access to alembic.ini values.
config = context.config

# Configure Python logging from alembic.ini [loggers] section.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the target metadata for autogenerate support.
target_metadata = Base.metadata


def get_database_url() -> str:
    """Load database URL from application settings (never from alembic.ini)."""
    from app.config.settings import get_settings
    return get_settings().database_url


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Generates migration SQL without connecting to the database.
    Useful for reviewing SQL before applying it.
    """
    url = get_database_url()
    context.configure(
        url=url,
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
    """Run migrations in 'online' mode using an async engine."""
    db_url = get_database_url()

    # Override the URL in config for async engine creation
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = db_url

    connectable = async_engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
