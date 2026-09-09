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

Phase 2 additions:
- Provider registry initialization in lifespan
- Chat completion router (/api/v1/chat/completions)
- Provider discovery router (/api/v1/providers)
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints.chat import router as chat_router
from app.api.v1.endpoints.health import router as system_router
from app.api.v1.endpoints.providers import router as providers_router
from app.config.settings import get_settings
from app.core.logging import configure_logging, logger
from app.database.session import close_db, init_db
from app.exceptions import register_exception_handlers
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.providers.registry import registry
from app.utils.redis_client import close_redis, init_redis

settings = get_settings()


def _init_providers() -> None:
    """
    Initialize and register LLM provider adapters.

    Active Phase 2 Providers:
      1. Gemini (Cloud SDK - requires GEMINI_API_KEY)
      2. Groq (Cloud SDK - requires GROQ_API_KEY)
      3. Ollama (Local HTTP - requires OLLAMA_BASE_URL)

    Missing credentials do NOT crash startup — the provider is simply
    not registered and will return INVALID_PROVIDER when requested.
    """
    from app.providers.gemini_provider import GeminiProvider
    from app.providers.groq_provider import GroqProvider
    from app.providers.ollama_provider import OllamaProvider

    if settings.gemini_available:
        registry.register(
            GeminiProvider(
                api_key=settings.gemini_api_key,
                timeout=settings.gemini_timeout_seconds,
            )
        )
    else:
        logger.info(
            "Gemini provider skipped (disabled or missing API key)",
        )

    if settings.groq_available:
        registry.register(
            GroqProvider(
                api_key=settings.groq_api_key,
                base_url=settings.groq_base_url,
                timeout=settings.groq_timeout_seconds,
            )
        )
    else:
        logger.info(
            "Groq provider skipped (disabled or missing API key)",
        )

    if settings.ollama_available:
        registry.register(
            OllamaProvider(
                base_url=settings.ollama_base_url,
                timeout=settings.ollama_timeout_seconds,
            )
        )
    else:
        logger.info(
            "Ollama provider skipped (disabled or missing base URL)",
        )

    registered = registry.provider_names
    logger.info(
        "Provider registry initialized: {providers}",
        providers=registered or ["none"],
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan manager.

    Startup:
        1. Configure structured logging.
        2. Initialise PostgreSQL connection pool.
        3. Initialise Redis client.
        4. Initialise LLM provider registry.

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
    _init_providers()

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
    application.include_router(chat_router, prefix="/api/v1")
    application.include_router(providers_router, prefix="/api/v1")

    return application


app = create_application()
