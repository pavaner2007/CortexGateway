<div align="center">

<img src="https://img.shields.io/badge/Cortex-Gateway-6366f1?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiIgZmlsbD0ibm9uZSI+PHJlY3Qgd2lkdGg9IjMyIiBoZWlnaHQ9IjMyIiByeD0iOCIgZmlsbD0iIzYzNjZmMSIvPjxwYXRoIGQ9Ik0xNiA2QzEwLjQ3NyA2IDYgMTAuNDc3IDYgMTZzNC40NzcgMTAgMTAgMTAgMTAtNC40NzcgMTAtMTBTMjEuNTIzIDYgMTYgNnptMCAzYTcgNyAwIDEgMSAwIDE0QTcgNyAwIDAgMSAxNiA5em0wIDJhNC41IDQuNSAwIDEgMCAwIDkgNC41IDQuNSAwIDAgMCAwLTl6bTAgMmEyLjUgMi41IDAgMSAxIDAgNSAyLjUgMi41IDAgMCAxIDAtNXoiIGZpbGw9IndoaXRlIi8+PC9zdmc+" alt="Cortex Gateway" />

# Cortex Gateway

### Intelligent Multi-LLM Gateway & AI Infrastructure Platform

[![Python](https://img.shields.io/badge/Python-3.12+-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61dafb?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178c6?style=flat-square&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7-dc382d?style=flat-square&logo=redis&logoColor=white)](https://redis.io)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ed?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

<br/>

*A production-quality gateway that sits between your applications and multiple LLM providers — unified routing, health monitoring, failover, rate limiting, cost tracking, and observability.*

</div>

---

## What is Cortex Gateway?

Cortex Gateway is a centralized AI infrastructure platform designed to give engineering teams complete control over their LLM usage. Instead of each application directly calling OpenAI, Gemini, Groq, or Anthropic, all traffic flows through Cortex Gateway — giving you a single place to manage routing, costs, reliability, and compliance.

```
Your Application
      │
      ▼
┌─────────────────────────────────────────────┐
│              Cortex Gateway                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Routing │  │ Rate Limit│  │Analytics │  │
│  └──────────┘  └──────────┘  └──────────┘  │
└──────┬──────────────┬──────────────┬─────────┘
       │              │              │
       ▼              ▼              ▼
    OpenAI         Gemini          Groq
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI · Python 3.12 · Uvicorn |
| **Database** | PostgreSQL 16 · SQLAlchemy 2.x · asyncpg |
| **Cache** | Redis 7 · redis-py async |
| **Config** | Pydantic Settings v2 |
| **Logging** | Loguru |
| **Frontend** | React 18 · TypeScript · Vite · Tailwind CSS |
| **Routing** | React Router v6 |
| **Testing** | pytest · pytest-asyncio · httpx |
| **Containers** | Docker · Docker Compose |

---

## Features

### Phase 1 — Infrastructure Foundation ✅
- ⚡ **Async FastAPI backend** with full lifespan management
- 🗄️ **PostgreSQL** with SQLAlchemy 2.x async engine and asyncpg driver
- ⚡ **Redis** async client with connection pooling
- 🔍 **Health monitoring** — independent concurrent checks for all dependencies
- 🆔 **Request ID propagation** — `X-Request-ID` header through every request
- 📋 **Structured logging** — timestamped, request-scoped, Loguru-powered
- 🛡️ **Global error handling** — consistent JSON error envelope, no stack traces exposed
- 📖 **API documentation** — Swagger UI at `/docs`, ReDoc at `/redoc`
- 🎨 **React dashboard** — live system status with 30s auto-polling
- 🐳 **Docker Compose** — full 4-service stack, one command to run

### Phase 2 — Unified Multi-LLM Gateway ✅
- 🤖 **Three provider adapters** — OpenAI, Google Gemini, Groq (all async)
- 🔌 **Provider abstraction** — `BaseLLMProvider` ABC, Open/Closed Principle
- 📋 **Provider registry** — register, retrieve, discover providers at runtime
- 🔀 **Unified chat API** — one endpoint, any provider, normalized response
- 📊 **Token usage normalization** — consistent `prompt/completion/total_tokens` across all providers
- ⏱️ **Latency tracking** — provider request duration in every response
- 🛡️ **Error normalization** — 8 typed error codes, correct HTTP status per error type
- 🔑 **Safe credential handling** — missing keys disable provider gracefully, never logged
- 🔍 **Provider discovery** — list providers, get details, list models per provider
- ✅ **99 automated tests** — all passing, zero real API credits required

### Coming Soon
- 🔐 Authentication & API key management
- 👥 Teams & organizations
- 🚦 Rate limiting & budget controls
- 🔄 Intelligent routing (cost/latency/capability-based)
- 💰 Cost tracking & analytics
- 📊 Prometheus metrics & OpenTelemetry tracing
- 🔄 Automatic failover & circuit breakers
- 🖥️ Admin dashboard

---

## Quick Start

### Prerequisites

| Tool | Version |
|------|---------|
| Docker | 24+ |
| Docker Compose | v2.20+ |

### Run with Docker

```bash
# 1. Clone the repository
git clone https://github.com/pavaner2007/CortexGateway.git
cd CortexGateway

# 2. Set up environment
cp backend/.env.example backend/.env
# Edit backend/.env — set POSTGRES_PASSWORD and SECRET_KEY

# 3. Start all services
docker compose up --build
```

That's it. All 4 services start automatically.

| Service | URL |
|---------|-----|
| 🖥️ Frontend Dashboard | http://localhost:5173 |
| ⚙️ Backend API | http://localhost:8000 |
| 📖 Swagger UI | http://localhost:8000/docs |
| 📚 ReDoc | http://localhost:8000/redoc |
| ❤️ Health Check | http://localhost:8000/health |

---

## Local Development

### Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Run with hot-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> The backend starts even without PostgreSQL or Redis — health checks will report `disconnected` until those services are available.

### Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

### Tests

```bash
cd backend
pytest tests/ -v
```

```
99 passed in 0.55s ✅
```

No Docker needed — all external dependencies are mocked.

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and configure:

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | `Cortex Gateway` | Application display name |
| `APP_VERSION` | `1.0.0` | Semantic version |
| `ENVIRONMENT` | `development` | `development` \| `production` |
| `POSTGRES_HOST` | `postgres` | PostgreSQL hostname |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `cortex_gateway` | Database name |
| `POSTGRES_USER` | `cortex_user` | Database user |
| `POSTGRES_PASSWORD` | — | ⚠️ **Change this** |
| `DATABASE_URL` | *(auto)* | Leave blank — auto-composed |
| `REDIS_HOST` | `redis` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_URL` | *(auto)* | Leave blank — auto-composed |
| `SECRET_KEY` | — | ⚠️ **Change this** (32+ chars) |
| `LOG_LEVEL` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |

### Provider Configuration (Phase 2)

| Variable | Default | Description |
|----------|---------|-------------|
| `PROVIDER_TIMEOUT_SECONDS` | `30` | Timeout for all provider requests |
| `DEFAULT_PROVIDER` | — | Optional default provider name |
| `DEFAULT_MODEL` | — | Optional default model |
| `OPENAI_API_KEY` | — | OpenAI API key (blank = disabled) |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI base URL |
| `OPENAI_ENABLED` | `true` | Enable/disable OpenAI |
| `GEMINI_API_KEY` | — | Google Gemini API key (blank = disabled) |
| `GEMINI_ENABLED` | `true` | Enable/disable Gemini |
| `GROQ_API_KEY` | — | Groq API key (blank = disabled) |
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` | Groq base URL |
| `GROQ_ENABLED` | `true` | Enable/disable Groq |

> A missing or blank API key disables the provider gracefully. The application starts normally and returns `INVALID_PROVIDER` when that provider is requested.

---

## API Reference

### `GET /`
Returns application info.
```json
{
  "name": "Cortex Gateway",
  "version": "1.0.0",
  "status": "running",
  "description": "Intelligent Multi-LLM Gateway and AI Infrastructure Platform",
  "environment": "development"
}
```

### `GET /health`
Independently checks all dependencies. Returns `200 OK` when healthy, `503 Service Unavailable` when degraded.
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "version": "1.0.0"
}
```

### `GET /version`
```json
{ "version": "1.0.0" }
```

---

## Phase 2 API — Unified Chat Completions

### `POST /api/v1/chat/completions`

Send a chat request to any provider using the same schema.

```bash
# Groq
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "groq",
    "model": "llama-3.3-70b-versatile",
    "messages": [{"role": "user", "content": "Explain Docker in simple terms."}],
    "temperature": 0.7,
    "max_tokens": 500
  }'

# Gemini
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "gemini",
    "model": "gemini-1.5-flash",
    "messages": [{"role": "user", "content": "Explain Docker in simple terms."}]
  }'

# OpenAI
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Explain Docker in simple terms."}]
  }'
```

**Normalized response (identical shape for all providers):**
```json
{
  "id": "ctx_abc123def456",
  "object": "chat.completion",
  "created": 1710000000,
  "provider": "groq",
  "model": "llama-3.3-70b-versatile",
  "choices": [{
    "index": 0,
    "message": {"role": "assistant", "content": "Docker is ..."},
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 85,
    "total_tokens": 97
  },
  "metadata": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "latency_ms": 423.5
  }
}
```

### `GET /api/v1/providers`
```json
{"providers": [{"name": "groq", "enabled": true, "available": true}, ...]}
```

### `GET /api/v1/providers/{provider}`
```json
{"name": "groq", "enabled": true, "available": true, "capabilities": ["chat"]}
```

### `GET /api/v1/providers/{provider}/models`
```json
{"provider": "groq", "models": ["llama-3.3-70b-versatile", "llama3-8b-8192", ...]}
```

### Error Response Format
```json
{
  "error": {
    "code": "PROVIDER_RATE_LIMITED",
    "message": "The selected provider is currently rate limited.",
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

| Error Code | HTTP | Cause |
|------------|------|-------|
| `INVALID_PROVIDER` | 404 | Provider not registered |
| `PROVIDER_DISABLED` | 503 | Provider explicitly disabled |
| `INVALID_MODEL` | 400 | Model not found on provider |
| `PROVIDER_TIMEOUT` | 504 | Request exceeded timeout |
| `PROVIDER_RATE_LIMITED` | 429 | Provider rate limit hit |
| `PROVIDER_UNAVAILABLE` | 503 | Provider service down |
| `PROVIDER_AUTHENTICATION_FAILED` | 502 | Invalid/missing API key |
| `PROVIDER_ERROR` | 502 | Generic upstream error |

Full API docs → http://localhost:8000/docs

---

## Project Structure

```
CortexGateway/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/
│   │   │   ├── health.py          # GET /, /version, /health
│   │   │   ├── chat.py            # POST /api/v1/chat/completions
│   │   │   └── providers.py       # GET /api/v1/providers/*
│   │   ├── config/
│   │   │   └── settings.py        # Pydantic Settings v2 (+ provider config)
│   │   ├── core/
│   │   │   └── logging.py         # Loguru configuration
│   │   ├── database/
│   │   │   └── session.py         # SQLAlchemy 2.x async engine
│   │   ├── middleware/
│   │   │   ├── request_id.py      # X-Request-ID propagation
│   │   │   └── logging.py         # Request/response logging
│   │   ├── providers/
│   │   │   ├── base.py            # BaseLLMProvider ABC
│   │   │   ├── registry.py        # ProviderRegistry singleton
│   │   │   ├── exceptions.py      # Typed provider exception hierarchy
│   │   │   ├── openai_provider.py # OpenAI async adapter
│   │   │   ├── gemini_provider.py # Google Gemini async adapter
│   │   │   └── groq_provider.py   # Groq async adapter
│   │   ├── schemas/
│   │   │   ├── responses.py       # Phase 1 shared Pydantic v2 models
│   │   │   └── chat.py            # Phase 2 chat request/response schemas
│   │   ├── services/
│   │   │   └── chat_service.py    # ChatService orchestration layer
│   │   ├── utils/
│   │   │   └── redis_client.py    # Async Redis client
│   │   ├── exceptions.py          # Global exception handlers
│   │   └── main.py                # FastAPI app + lifespan
│   ├── tests/
│   │   ├── conftest.py            # Fixtures (DB/Redis mocked)
│   │   ├── test_endpoints.py      # 33 Phase 1 endpoint tests
│   │   ├── test_providers.py      # 32 provider unit tests
│   │   └── test_chat_api.py       # 34 Phase 2 API tests
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pytest.ini
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── api/health.ts          # Type-safe API client
│   │   ├── components/
│   │   │   ├── Layout.tsx         # Sidebar + header shell
│   │   │   └── StatusCard.tsx     # Reusable status card
│   │   └── pages/
│   │       └── Dashboard.tsx      # Live health dashboard
│   ├── Dockerfile
│   ├── package.json
│   └── vite.config.ts
│
├── docs/
│   └── architecture.md
├── docker-compose.yml
└── README.md
```

---

## Roadmap

| # | Feature | Status |
|---|---------|--------|
| 1 | Infrastructure Foundation | ✅ **Done** |
| 2 | Unified Multi-LLM Gateway | ✅ **Done** |
| 3 | Intelligent Routing Engine | 🔜 Next |
| 4 | Authentication & API Keys | ⏳ Planned |
| 5 | Teams & Organizations | ⏳ Planned |
| 6 | Rate Limiting & Budgets | ⏳ Planned |
| 7 | Provider Failover & Circuit Breakers | ⏳ Planned |
| 8 | Cost Tracking & Analytics | ⏳ Planned |
| 9 | Prometheus & OpenTelemetry | ⏳ Planned |
| 10 | Admin Dashboard | ⏳ Planned |

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first.

1. Fork the repo
2. Create your branch: `git checkout -b feat/your-feature`
3. Commit your changes: `git commit -m 'feat: add your feature'`
4. Push: `git push origin feat/your-feature`
5. Open a Pull Request

---

## License

MIT © 2026 [Cortex Gateway Contributors](LICENSE)
