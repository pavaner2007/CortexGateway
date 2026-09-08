"""
Cortex Gateway — FastAPI Application Entry Point.

Configures:
- Application metadata (name, version, description)
- Lifespan management (startup / shutdown)
- CORS
- Middleware (Request ID, Request Logging)
- Global exception handlers
- API router registration
- Swagger / ReDoc documentation
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints.health import router as system_router
from app.config.settings import get_settings
from app.core.logging import configure_logging, logger
from app.database.session import close_db, init_db
from app.exceptions import register_exception_handlers
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.utils.redis_client import close_redis, init_redis

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan manager.

    Startup:
        1. Configure structured logging.
        2. Initialise PostgreSQL connection pool.
        3. Initialise Redis client.

    Shutdown:
        1. Dispose PostgreSQL connection pool.
        2. Close Redis client.
    """
    # ── Startup ──────────────────────────────────────────────────────────────
    configure_logging()
    logger.info(
        "Starting {name} v{version} [{env}]",
        name=settings.app_name,
        version=settings.app_version,
        env=settings.environment,
    )

    init_db()
    init_redis()

    logger.info("Application startup complete")
    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("Shutting down application …")
    await close_db()
    await close_redis()
    logger.info("Application shutdown complete")


def create_application() -> FastAPI:
    """Factory function that creates and configures the FastAPI application."""

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=settings.app_description,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # ── Custom middleware (applied in reverse registration order) ─────────────
    # RequestIDMiddleware runs first (outermost) so the ID is available to
    # RequestLoggingMiddleware and all downstream handlers.
    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(RequestIDMiddleware)

    # ── Global exception handlers ─────────────────────────────────────────────
    register_exception_handlers(application)

    # ── Routers ───────────────────────────────────────────────────────────────
    application.include_router(system_router)

    return application


app = create_application()
