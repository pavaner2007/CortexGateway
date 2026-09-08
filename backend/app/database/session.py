"""
Cortex Gateway — Async PostgreSQL Database Session.

Provides:
- Async SQLAlchemy engine (asyncpg driver)
- Async session factory
- FastAPI dependency: ``get_db_session``
- Health-check helper: ``check_db_health``
- Lifecycle helpers: ``init_db`` / ``close_db``

No domain models are created here — this module is purely connection
infrastructure and is intentionally kept free of business-logic tables.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.settings import get_settings
from app.core.logging import logger

# Module-level engine and session factory — initialised during lifespan startup.
_engine = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db() -> None:
    """
    Create the async SQLAlchemy engine and session factory.
    Must be called once during application startup.
    """
    global _engine, _async_session_factory

    settings = get_settings()

    _engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,          # SQL query logging in debug mode only
        pool_pre_ping=True,           # detect stale connections before use
        pool_size=5,
        max_overflow=10,
    )

    _async_session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,       # keep ORM objects usable after commit
        autocommit=False,
        autoflush=False,
    )

    logger.info("Database engine initialised", host=settings.postgres_host)


async def close_db() -> None:
    """Dispose the connection pool gracefully during application shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        logger.info("Database engine disposed")


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context-manager that yields a database session.
    Also usable as a FastAPI dependency via ``Depends(get_db_session)``.
    """
    if _async_session_factory is None:
        raise RuntimeError("Database is not initialised. Call init_db() first.")

    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_db_health() -> str:
    """
    Perform a lightweight connectivity check (``SELECT 1``).

    Returns:
        ``"connected"``  — PostgreSQL is reachable.
        ``"disconnected"`` — PostgreSQL is unreachable (never raises).
    """
    if _engine is None:
        return "disconnected"
    try:
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "connected"
    except Exception as exc:
        logger.warning("Database health check failed", error=str(exc))
        return "disconnected"
