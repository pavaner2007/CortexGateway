# Cortex Gateway — Phase 1 Architecture

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
