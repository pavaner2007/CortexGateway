# Cortex Gateway — Architecture (Phase 1 + Phase 2)

## Overview

Phase 1 establishes the production foundation: a clean, async FastAPI backend
connected to PostgreSQL and Redis, a React dashboard frontend, and a Docker
Compose stack — with no LLM business logic yet.

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         Client Browser                        │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTP (port 5173)
                         ▼
┌──────────────────────────────────────────────────────────────┐
│              React Frontend (Vite + Tailwind)                 │
│   Dashboard → StatusCard × 4 (overall, db, redis, version)   │
│   Polls GET /health every 30s                                 │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTP (port 8000)
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                   FastAPI Backend                              │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ASGI Middleware Stack (applied outer → inner)       │    │
│  │  1. CORSMiddleware                                   │    │
│  │  2. RequestIDMiddleware   (X-Request-ID)             │    │
│  │  3. RequestLoggingMiddleware                         │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Exception Handlers                                  │    │
│  │  • RequestValidationError → 422                      │    │
│  │  • HTTPException → propagated status                 │    │
│  │  • Exception (catch-all) → 500                       │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  API Router (app/api/v1/endpoints/health.py)         │    │
│  │  GET /         → RootResponse                        │    │
│  │  GET /version  → VersionResponse                     │    │
│  │  GET /health   → HealthResponse (200 or 503)         │    │
│  └─────────────────────────────────────────────────────┘    │
└──────┬──────────────────────────────┬───────────────────────┘
       │                              │
       ▼                              ▼
┌─────────────────┐     ┌────────────────────┐
│   PostgreSQL 16  │     │     Redis 7         │
│   (asyncpg)      │     │  (redis-py async)   │
│   port 5432      │     │  port 6379          │
└─────────────────┘     └────────────────────┘
```

---

## Backend Module Architecture

```
backend/app/
├── config/
│   └── settings.py          Pydantic Settings v2
│                            - Loads from .env / environment variables
│                            - Auto-composes DATABASE_URL and REDIS_URL
│                            - Single lru_cache singleton
│
├── core/
│   └── logging.py           Loguru structured logging
│                            - Single stderr sink
│                            - Level from LOG_LEVEL env var
│                            - No stack traces, no secrets
│
├── database/
│   └── session.py           SQLAlchemy 2.x async engine
│                            - init_db() / close_db() lifecycle
│                            - async_sessionmaker
│                            - check_db_health() → "connected"|"disconnected"
│
├── utils/
│   └── redis_client.py      Async Redis client
│                            - init_redis() / close_redis() lifecycle
│                            - check_redis_health() → "connected"|"disconnected"
│
├── middleware/
│   ├── request_id.py        X-Request-ID propagation
│   │                        - Reads or generates UUID v4
│   │                        - Stores in ContextVar
│   │                        - Adds to response header
│   │
│   └── logging.py           Request/response logging
│                            - method, path, status, duration, client_ip
│                            - Uses request_id from ContextVar
│
├── schemas/
│   └── responses.py         Shared Pydantic v2 response models
│                            - RootResponse, VersionResponse, HealthResponse
│                            - ErrorDetail, ErrorResponse
│
├── exceptions.py            Global exception handlers
│                            - Consistent {"error": {...}} envelope
│                            - 3 handlers: validation, http, catch-all
│
└── main.py                  FastAPI application factory
                             - lifespan context manager
                             - CORS, middleware, routers, exception handlers
```

---

## PostgreSQL Connection Flow

```
Application startup (lifespan)
    │
    ▼
init_db()
    │
    ├── create_async_engine(DATABASE_URL, pool_pre_ping=True)
    │
    └── async_sessionmaker(engine)

GET /health request
    │
    ▼
check_db_health()
    │
    ├── engine.connect()
    │       │
    │       └── SELECT 1
    │               │
    │       ┌───────┴──────┐
    │       ▼              ▼
    │  "connected"   Exception caught
    │                      │
    │               "disconnected"
    │                      │
    └───────────────────────
    ▼
Return status string (never raises)

Application shutdown (lifespan)
    │
    └── close_db() → engine.dispose()
```

---

## Redis Connection Flow

```
Application startup (lifespan)
    │
    ▼
init_redis()
    │
    └── aioredis.from_url(REDIS_URL)

GET /health request
    │
    ▼
check_redis_health()
    │
    ├── redis_client.ping()
    │       │
    │   ┌───┴───┐
    │   ▼       ▼
    │  True  Exception caught
    │   │        │
    │ "connected" "disconnected"
    │   │        │
    └───┴────────┘
    ▼
Return status string (never raises)

Application shutdown (lifespan)
    │
    └── close_redis() → redis_client.aclose()
```

---

## Request ID Flow

```
Incoming request
    │
    ▼
RequestIDMiddleware.dispatch()
    │
    ├── Read X-Request-ID header
    │       │
    │   Present?
    │   ├── Yes → use provided ID
    │   └── No  → generate UUID v4
    │
    ├── _request_id_ctx.set(request_id)   ← ContextVar (per-task)
    │
    ├── await call_next(request)           ← route handler runs
    │       │
    │       └── (any code can call get_request_id() here)
    │
    └── response.headers["X-Request-ID"] = request_id
                │
                ▼
            Client receives X-Request-ID in response
```

---

## Health Check Flow

```
GET /health
    │
    ▼
asyncio.gather(
    check_db_health(),      ─┐
    check_redis_health()    ─┤  run concurrently
)                            │
    │                        │
    ▼                        │
Both results collected  ─────┘
    │
    ├── db="connected", redis="connected"
    │       → status="healthy", HTTP 200
    │
    └── any "disconnected"
            → status="degraded", HTTP 503
    │
    ▼
JSONResponse(HealthResponse)
```

---

## Error Handling Flow

```
Exception raised anywhere in route handler
    │
    ▼
FastAPI exception handler dispatch
    │
    ├── RequestValidationError
    │       → 422 + {"error": {"code": "VALIDATION_ERROR", ...}}
    │
    ├── HTTPException
    │       → (status code) + {"error": {"code": "NOT_FOUND", ...}}
    │
    └── Exception (catch-all)
            → 500 + {"error": {"code": "INTERNAL_SERVER_ERROR", ...}}
            → exception logged internally (Loguru)
            → NO stack trace in response
            → NO internal details in response
```

---

## Frontend Architecture

```
src/
├── api/
│   └── health.ts            Type-safe fetch wrappers
│                            fetchHealth() → HealthData
│                            fetchRoot()   → RootData
│
├── components/
│   ├── Layout.tsx           Dark glass sidebar + sticky top bar
│   └── StatusCard.tsx       Reusable card with variant-driven
│                            color/animation (healthy/degraded/loading)
│
├── pages/
│   └── Dashboard.tsx        Polls GET /health every 30s
│                            4 status cards + API quick links
│                            Loading / error states
│
├── App.tsx                  BrowserRouter + Routes
└── main.tsx                 React 18 createRoot
```

---

## Key Technology Choices

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Backend framework | FastAPI 0.115 | Async-native, Pydantic v2, built-in OpenAPI |
| DB driver | asyncpg | Fastest PostgreSQL async driver for Python |
| ORM | SQLAlchemy 2.x | Async session support, mature ecosystem |
| Redis client | redis-py async | Official async client, simple API |
| Settings | pydantic-settings | Type-safe env loading, auto-compose URLs |
| Logging | Loguru | Structured, async-safe, zero boilerplate |
| Frontend | React 18 + Vite + Tailwind | Fast HMR, utility CSS, strong TS support |
| Containers | Docker Compose v2 | Local orchestration with health checks |

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | `Cortex Gateway` | Application display name |
| `APP_VERSION` | `1.0.0` | Semantic version |
| `ENVIRONMENT` | `development` | Runtime environment |
| `DEBUG` | `false` | Enable debug mode (SQL logging) |
| `API_HOST` | `0.0.0.0` | Uvicorn bind host |
| `API_PORT` | `8000` | Uvicorn bind port |
| `POSTGRES_HOST` | `postgres` | PostgreSQL hostname |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `cortex_gateway` | PostgreSQL database name |
| `POSTGRES_USER` | `cortex_user` | PostgreSQL username |
| `POSTGRES_PASSWORD` | — | PostgreSQL password (**change this**) |
| `DATABASE_URL` | _(auto)_ | Override auto-composed URL |
| `REDIS_HOST` | `redis` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_URL` | _(auto)_ | Override auto-composed URL |
| `SECRET_KEY` | — | Application secret (**change this**) |
| `LOG_LEVEL` | `INFO` | Loguru log level |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated CORS origins |

---

## Phase 2 — Unified Multi-LLM Gateway

### Request Flow

```
Client
   │
   ▼ POST /api/v1/chat/completions
RequestIDMiddleware           ← sets ContextVar (UUID v4)
RequestLoggingMiddleware      ← logs method, path, status
   │
   ▼
ChatCompletionRequest         ← Pydantic v2 validation
   │
   ▼
chat.py (endpoint)            ← ZERO provider logic
   │ Depends(get_registry)
   ▼
ChatService.complete()        ← orchestration only
   │ registry.get(provider)
   ▼
ProviderRegistry              ← O(1) dict lookup
   │
   ├── raises InvalidProviderError if not registered
   │
   ▼
BaseLLMProvider.chat(request, request_id)
   │
   ├── GeminiProvider      → google-generativeai Cloud SDK
   ├── GroqProvider        → AsyncGroq Cloud SDK
   └── OllamaProvider      → httpx.AsyncClient (Local / Self-Hosted REST API)
               │
               ▼
       Provider API
               │
               ▼
   Response normalization    ← inside each adapter
               │
               ▼
   ChatCompletionResponse    ← Cortex schema
   (identical shape for all providers)
               │
               ▼
   RequestLoggingMiddleware  ← logs latency
               │
               ▼
           Client
```

---

### Provider Abstraction Design

```python
# All providers implement:
class BaseLLMProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...          # canonical name: "gemini", "groq", "ollama"

    @abstractmethod
    async def chat(request, request_id) -> ChatCompletionResponse: ...

    @abstractmethod
    async def health_check() -> bool: ...

    @abstractmethod
    async def list_models() -> list[str]: ...
```

**Key invariant**: Routes and `ChatService` only ever call `BaseLLMProvider` methods.
The same `BaseLLMProvider` contract seamlessly supports both cloud-hosted API providers (Gemini, Groq) and local self-hosted runtimes (Ollama).

---

### Provider Registry

```
ProviderRegistry (module-level singleton)
    ├── _providers: dict[str, BaseLLMProvider]
    │
    ├── register(provider)   → dict insert, logged
    ├── get(name)            → raises InvalidProviderError if absent
    ├── is_registered(name)  → bool
    ├── list_providers()     → [ProviderInfo] (no secrets)
    └── provider_names       → sorted list of names

Initialized in lifespan startup:
    for each provider:
        if available (API key present for cloud, or base URL for local):
            registry.register(Provider(...))
        else:
            log "skipped" (graceful — no crash)
```

---

### Response Normalization

Every provider adapter produces the exact same `ChatCompletionResponse`:

```
ChatCompletionResponse
├── id               "ctx_" + 12 hex chars
├── object           "chat.completion"
├── created          Unix timestamp
├── provider         "gemini" | "groq" | "ollama"
├── model            exact model string from provider
├── choices[]
│   ├── index        0-based
│   ├── message
│   │   ├── role     "assistant"
│   │   └── content  text content
│   └── finish_reason  "stop" | "length" | None
├── usage
│   ├── prompt_tokens     int | None
│   ├── completion_tokens int | None
│   └── total_tokens      int | None
└── metadata
    ├── request_id   from ContextVar (X-Request-ID)
    └── latency_ms   provider request duration in milliseconds
```

**Token usage is Optional** — never fabricated.
- **Ollama**: uses `prompt_eval_count` → `prompt_tokens`, `eval_count` → `completion_tokens`.
- **Gemini**: uses `candidates_token_count` → `completion_tokens`.
- **Groq**: uses `usage.prompt_tokens`, `usage.completion_tokens`.

---

### Error Normalization

```
ProviderException (base)
    │
    ├── InvalidProviderError         code=INVALID_PROVIDER        HTTP 404
    ├── ProviderDisabledError        code=PROVIDER_DISABLED        HTTP 503
    ├── InvalidModelError            code=INVALID_MODEL           HTTP 400
    ├── ProviderTimeoutError         code=PROVIDER_TIMEOUT        HTTP 504
    ├── ProviderRateLimitError       code=PROVIDER_RATE_LIMITED   HTTP 429
    ├── ProviderUnavailableError     code=PROVIDER_UNAVAILABLE    HTTP 503
    ├── ProviderAuthError            code=PROVIDER_AUTHENTICATION_FAILED HTTP 502
    └── ProviderError                code=PROVIDER_ERROR          HTTP 502

All exceptions caught by:
    register_exception_handlers(app)
        └── @app.exception_handler(ProviderException)
                → _error_response(exc.status_code, exc.code, exc.message, request_id)
                → {"error": {"code": "...", "message": "...", "request_id": "..."}}

API keys NEVER appear in error messages or logs.
Provider stack traces NEVER reach the client.
```

---

### How to Add a New Provider (Phase 3+)

1. **Create** `backend/app/providers/{name}_provider.py`
2. **Implement** `BaseLLMProvider` — all 4 abstract methods
3. **Translate** provider errors to `ProviderException` subclasses in `_raise_from_status()`
4. **Add** config to `Settings`: `{name}_api_key` or `{name}_base_url`, `{name}_enabled`, `{name}_available`
5. **Register** in `main._init_providers()`
6. **Add** to `app/providers/__init__.py` exports
7. **Add** tests in `tests/test_providers.py`

**No changes needed in**: routes, ChatService, ProviderRegistry, exception handlers,
schemas, or any existing provider.

---

## Phase 2 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROVIDER_TIMEOUT_SECONDS` | `30` | Timeout for all provider HTTP requests |
| `DEFAULT_PROVIDER` | — | Reserved for Phase 3 routing |
| `DEFAULT_MODEL` | — | Reserved for Phase 3 routing |
| `GEMINI_API_KEY` | — | Google Gemini API key |
| `GEMINI_ENABLED` | `true` | Enable/disable Gemini |
| `GROQ_API_KEY` | — | Groq API key |
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` | Groq base URL |
| `GROQ_ENABLED` | `true` | Enable/disable Groq |
| `OLLAMA_ENABLED` | `true` | Enable/disable Ollama |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama URL (`http://ollama:11434` in Docker) |
| `OLLAMA_TIMEOUT_SECONDS` | `60` | Ollama-specific request timeout |

