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

Phase 2:  Provider registry + chat/provider routers
Phase 5:  Bootstrap, organizations, teams, API key routers
Phase 6:  Rate limiting and budget management
Phase 7:  Prometheus metrics endpoint, analytics routers, OTel tracing init
Phase 8:  Admin dashboard backend APIs
Phase 9A: Model Registry — DB-backed catalog with admin CRUD and shared metadata
Phase 9B: Semantic Caching — Redis-backed vector similarity cache for chat responses
Phase 9C: Policy Engine — declarative team policy (routing, fallback, budget, cache)
Phase 9D: A/B Testing & Canary — deterministic SHA-256 traffic splitting across model arms
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints.analytics import router as analytics_router
from app.api.v1.endpoints.api_keys import router as api_keys_router
from app.api.v1.endpoints.auth_me import router as auth_me_router
from app.api.v1.endpoints.bootstrap import router as bootstrap_router
from app.api.v1.endpoints.budget import router as budget_router
from app.api.v1.endpoints.rate_limits import router as rate_limits_router
from app.api.v1.endpoints.chat import router as chat_router
from app.api.v1.endpoints.health import router as system_router
from app.api.v1.endpoints.metrics import router as metrics_router
from app.api.v1.endpoints.model_registry import router as model_registry_router
from app.api.v1.endpoints.organizations import router as organizations_router
from app.api.v1.endpoints.providers import router as providers_router
from app.api.v1.endpoints.teams import router as teams_router
from app.api.v1.endpoints.policy import router as policy_router
from app.config.settings import get_settings
from app.core.logging import configure_logging, logger
from app.database.session import close_db, get_db_session, init_db
from app.exceptions import register_exception_handlers
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.providers.registry import registry
from app.semantic_cache.cache import SemanticCache, build_semantic_cache
from app.utils.redis_client import close_redis, init_redis

settings = get_settings()

# Phase 9B: module-level semantic cache singleton
# Populated during lifespan startup; None until then.
_semantic_cache: SemanticCache | None = None


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


async def _init_model_catalog() -> None:
    """
    Load the ModelMetadataCatalog from the model_registry DB table.

    Called once at startup to populate the in-memory catalog used by
    Phase 3 routing and Phase 6 cost calculation.
    """
    from app.routing.metadata import _shared_catalog
    try:
        async with get_db_session() as session:
            await _shared_catalog.load_from_db(session)
        logger.info(
            "ModelMetadataCatalog loaded from DB",
            total=_shared_catalog.size,
        )
    except Exception as exc:
        logger.warning(
            "ModelMetadataCatalog initial load failed — routing will use empty catalog",
            error=str(exc),
        )


async def _catalog_refresh_loop() -> None:
    """
    Background task: refresh the ModelMetadataCatalog every 60 seconds.

    Runs indefinitely until cancelled during application shutdown.
    Failures are logged as warnings and never crash the application.
    """
    import asyncio
    from app.routing.metadata import _shared_catalog

    while True:
        await asyncio.sleep(60)
        try:
            async with get_db_session() as session:
                await _shared_catalog.load_from_db(session)
            logger.debug(
                "ModelMetadataCatalog background refresh complete",
                total=_shared_catalog.size,
            )
        except Exception as exc:
            logger.warning(
                "ModelMetadataCatalog background refresh failed",
                error=str(exc),
            )


def _init_tracing() -> None:
    """
    Initialize OpenTelemetry tracing.

    When OTEL_ENABLED=false (default): installs no-op tracer.
    When OTEL_ENABLED=true: installs OTLP gRPC exporter pointed at
    OTEL_EXPORTER_OTLP_ENDPOINT.

    Gateway works normally when collector is unavailable.
    """
    from app.observability.tracing import init_tracing

    init_tracing(
        enabled=settings.otel_enabled,
        service_name=settings.otel_service_name,
        otlp_endpoint=settings.otel_exporter_otlp_endpoint,
    )
    logger.info(
        "OpenTelemetry tracing initialized",
        enabled=settings.otel_enabled,
        service=settings.otel_service_name,
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
        5. Initialise OpenTelemetry tracing (Phase 7).

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
    _init_tracing()

    # Phase 9A — load model catalog from DB (after DB is initialised)
    await _init_model_catalog()

    # Phase 9A — start background catalog refresh every 60 s
    import asyncio
    refresh_task = asyncio.create_task(_catalog_refresh_loop())

    # Phase 9B — initialize semantic cache singleton
    global _semantic_cache
    from app.utils.redis_client import _redis_client  # available after init_redis()
    _semantic_cache = build_semantic_cache(redis=_redis_client, settings=settings)
    logger.info(
        "Semantic cache initialized",
        enabled=settings.semantic_cache_enabled,
        version=settings.semantic_cache_version,
        embedding_model=settings.semantic_cache_embedding_model,
    )

    logger.info("Application startup complete")
    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("Shutting down application …")
    refresh_task.cancel()
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
    # Public (no auth required)
    application.include_router(system_router)

    # Phase 7 — Prometheus metrics (unauthenticated, standard convention)
    application.include_router(metrics_router)

    # Phase 2 — provider + chat (chat now requires auth)
    application.include_router(chat_router, prefix="/api/v1")
    application.include_router(providers_router, prefix="/api/v1")

    # Phase 5 — bootstrap + multi-tenancy management
    application.include_router(bootstrap_router, prefix="/api/v1")
    application.include_router(organizations_router, prefix="/api/v1")
    application.include_router(teams_router, prefix="/api/v1")
    application.include_router(api_keys_router, prefix="/api/v1")

    # Phase 6 — rate limiting + budget management
    application.include_router(budget_router, prefix="/api/v1")
    application.include_router(rate_limits_router, prefix="/api/v1")

    # Phase 7 — analytics (admin only, org-scoped)
    application.include_router(analytics_router, prefix="/api/v1")

    # Phase 8 — auth/me (dashboard login validation)
    application.include_router(auth_me_router, prefix="/api/v1")

    # Phase 9A — model registry (admin only)
    application.include_router(model_registry_router, prefix="/api/v1")

    # Phase 9C — team policy engine (admin only)
    application.include_router(policy_router, prefix="/api/v1")

    return application


app = create_application()
