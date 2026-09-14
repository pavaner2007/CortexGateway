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
     Gemini          Groq          Ollama
    (Cloud)        (Cloud)         (Local)
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
| **Testing** | pytest · pytest-asyncio · httpx · respx |
| **Containers** | Docker · Docker Compose · Ollama |

---

## Features

### Phase 1 — Infrastructure Foundation [Done]
- **Async FastAPI backend** with full lifespan management
- **PostgreSQL** with SQLAlchemy 2.x async engine and asyncpg driver
- **Redis** async client with connection pooling
- **Health monitoring** — independent concurrent checks for all dependencies
- **Request ID propagation** — `X-Request-ID` header through every request
- **Structured logging** — timestamped, request-scoped, Loguru-powered
- **Global error handling** — consistent JSON error envelope, no stack traces exposed
- **API documentation** — Swagger UI at `/docs`, ReDoc at `/redoc`
- **React dashboard** — live system status with 30s auto-polling
- **Docker Compose** — full multi-service stack, one command to run

### Phase 2 — Unified Multi-LLM Gateway [Done]
- **Three active provider adapters** — Google Gemini (Cloud), Groq (Cloud), Ollama (Local / Self-hosted)
- **Provider abstraction** — `BaseLLMProvider` ABC, Open/Closed Principle supporting cloud and local runtimes
- **Provider registry** — register, retrieve, discover providers at runtime
- **Unified chat API** — one endpoint, any provider, normalized response
- **Token usage normalization** — consistent `prompt/completion/total_tokens` across all providers
- **Latency tracking** — provider request duration in every response
- **Error normalization** — 8 typed error codes, correct HTTP status per error type
- **Safe credential handling** — missing keys disable cloud providers gracefully, zero keys needed for Ollama
- **Provider & Model discovery** — list providers, get details, dynamic model discovery (including local Ollama models)

### Phase 3 — Intelligent Routing Engine [Done]
- **6 Dynamic Routing Modes**:
  - `auto`: Balanced multi-factor scoring across health (30%), success rate (30%), latency (20%), and cost (20%).
  - `lowest_latency`: Response speed prioritized (60% latency weight, selects ultra-fast models like Groq Llama 3.1 8B Instant).
  - `lowest_cost`: Cost-efficiency prioritized (60% cost weight, prioritizes free self-hosted Ollama models).
  - `best_available`: Reliability maximized (80% health + success rate combined).
  - `capability_based`: Strict pre-filtering for required modalities (e.g., `vision`, `json`, `code`, `function_calling`).
  - `manual`: Direct bypass with deterministic explicit provider + model targeting.
- **Capability Pre-filtering** — Incompatible candidates are discarded before scoring (e.g. vision tasks route strictly to multimodal models).
- **Runtime Rolling Statistics** — In-memory rolling tracker for request volume, success rates, and exponential moving average latency.
- **Deterministic Tie-Breaking & Cold Start** — Multi-tiered deterministic tie-breaker guarantees repeatable routing decisions.
- **Routing Metadata Propagation** — Responses include `routing_mode` for full client observability.

### Phase 4 — Reliability and Resilience [Done]
- **Provider-Specific Timeouts** — Independently configurable timeouts for Gemini (30s), Groq (30s), and Ollama (60s).
- **Total Request Deadline** — Configurable maximum request deadline (120s) preventing unbounded retry and failover chains.
- **Transient Failure Classification** — Retries only on network drops, timeouts, 5xx server errors, and service outages; client 4xx errors fast-fail without retry.
- **Exponential Backoff & Jitter** — Non-blocking async sleep with randomized jitter to mitigate synchronized retry storms.
- **In-Memory Circuit Breaker** — 3-state machine (CLOSED, OPEN, HALF_OPEN) per provider. Tripped OPEN circuits fast-fail immediately without network calls or cascading slowness.
- **Automated Failover via Phase 3 Scorer** — Exhausted retries or tripped circuits automatically trigger next-best candidate discovery from Phase 3 router with loop prevention.
- **Capability-Preserving Fallback** — Fallbacks strictly satisfy original request capability constraints (e.g., vision).
- **Rich Reliability Metadata** — Responses carry `selected_provider`, `original_provider`, `failover_triggered`, `retry_count`, `failover_attempts`, and `circuit_breaker_state`.
- **154 automated tests** — 100% passing across Phase 1, Phase 2, Phase 3, and Phase 4 with zero real API credits required.
- **Code quality** — dead code removed, async lock protection added to circuit breaker state machine.

### Phase 5 — Authentication & Multi-Tenancy [Done]
- **API Key Authentication** — Bearer token auth on every protected endpoint (`Authorization: Bearer cxg_...`)
- **CSPRNG key generation** — cryptographically secure, URL-safe keys with `cxg_` prefix
- **HMAC-SHA256 hashing** — server-side pepper + `hmac.compare_digest` constant-time verification (timing-attack resistant)
- **Organizations & Teams** — full tenant hierarchy (1 org → N teams → N API keys)
- **RBAC** — `admin` and `member` roles; admin-only endpoints strictly enforced server-side
- **API Key Lifecycle** — create, list (metadata only), revoke (soft-delete); plaintext shown exactly once at creation
- **Bootstrap endpoint** — `POST /api/v1/bootstrap` creates first org + team + admin key in one call; guarded by `CORTEX_BOOTSTRAP_TOKEN`; auto-disabled after first org exists
- **Cross-tenant isolation** — server enforces org/team ownership; no client-supplied identity is trusted
- **Zero key-hash exposure** — `key_hash` field never appears in any API response (schema + integration tested)
- **Context propagation** — `RequestContext` (org_id, team_id, key_id, role) flows through every request via ContextVar
- **Alembic migrations** — async migration setup for `organizations`, `teams`, `api_keys` tables with FK cascade
- **201 automated tests** — 100% passing across all 5 phases; 42 new Phase 5 tests (security, lifecycle, RBAC, leakage)

### Planned Features
- Rate limiting & budget controls per team
- Cost tracking & persistent database analytics
- Prometheus metrics & OpenTelemetry tracing
- Full Admin dashboard

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
| Frontend Dashboard | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Health Check | http://localhost:8000/health |

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
201 passed in 3.84s
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
| `POSTGRES_PASSWORD` | — | **Change this** |
| `DATABASE_URL` | *(auto)* | Leave blank — auto-composed |
| `REDIS_HOST` | `redis` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_URL` | *(auto)* | Leave blank — auto-composed |
| `SECRET_KEY` | — | **Change this** (32+ chars) |
| `LOG_LEVEL` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |

### Provider Configuration (Phase 2)

| Variable | Default | Description |
|----------|---------|-------------|
| `PROVIDER_TIMEOUT_SECONDS` | `30` | Timeout for all provider requests |
| `DEFAULT_PROVIDER` | — | Optional default provider name |
| `DEFAULT_MODEL` | — | Optional default model |
| `GEMINI_API_KEY` | — | Google Gemini API key (blank = disabled) |
| `GEMINI_ENABLED` | `true` | Enable/disable Gemini |
| `GEMINI_TIMEOUT_SECONDS` | `30` | Gemini-specific request timeout |
| `GROQ_API_KEY` | — | Groq API key (blank = disabled) |
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` | Groq base URL |
| `GROQ_ENABLED` | `true` | Enable/disable Groq |
| `GROQ_TIMEOUT_SECONDS` | `30` | Groq-specific request timeout |
| `OLLAMA_ENABLED` | `true` | Enable/disable Ollama |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama base URL (`http://ollama:11434` in Docker) |
| `OLLAMA_TIMEOUT_SECONDS` | `60` | Ollama-specific request timeout |

> **Cloud Providers (Gemini, Groq):** A missing or blank API key disables the provider gracefully.  
> **Local Provider (Ollama):** Requires no API key. Ensure Ollama is running and has models pulled.

### Routing Configuration (Phase 3)

| Variable | Default | Description |
|----------|---------|-------------|
| `ROUTING_ENABLED` | `true` | Enable intelligent routing engine |
| `ROUTING_DEFAULT_MODE` | `auto` | Default mode: `auto` \| `lowest_cost` \| `lowest_latency` \| `best_available` \| `capability_based` |
| `ROUTING_HEALTH_WEIGHT` | `0.30` | Weight for provider health in scoring |
| `ROUTING_SUCCESS_RATE_WEIGHT` | `0.30` | Weight for historical success rate in scoring |
| `ROUTING_LATENCY_WEIGHT` | `0.20` | Weight for latency in scoring |
| `ROUTING_COST_WEIGHT` | `0.20` | Weight for cost per 1k tokens in scoring |
| `ROUTING_OLLAMA_COST_PER_1K` | `0.00` | Configurable cost for local Ollama models |

### Reliability Configuration (Phase 4)

| Variable | Default | Description |
|----------|---------|-------------|
| `RELIABILITY_TOTAL_REQUEST_TIMEOUT_SECONDS` | `120` | Hard deadline for entire request (retries + failovers) |
| `RELIABILITY_MAX_RETRIES` | `2` | Maximum retry attempts per provider |
| `RELIABILITY_RETRY_BASE_DELAY_SECONDS` | `0.25` | Base delay for exponential backoff |
| `RELIABILITY_RETRY_MAX_DELAY_SECONDS` | `2.0` | Maximum backoff delay cap |
| `RELIABILITY_RETRY_JITTER` | `true` | Add randomized jitter to backoff delays |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Consecutive failures before circuit trips OPEN |
| `CIRCUIT_BREAKER_COOLDOWN_SECONDS` | `30.0` | Seconds before OPEN circuit transitions to HALF_OPEN |
| `CIRCUIT_BREAKER_HALF_OPEN_TRIALS` | `1` | Trial requests allowed in HALF_OPEN state |
| `RELIABILITY_MAX_FAILOVER_ATTEMPTS` | `2` | Maximum failover candidates tried per request |

### Authentication Configuration (Phase 5)

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY_PEPPER` | — | **Change this** — HMAC-SHA256 pepper for key hashing. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `CORTEX_BOOTSTRAP_ENABLED` | `true` | Enable bootstrap endpoint. Set to `false` after first org is created |
| `CORTEX_BOOTSTRAP_TOKEN` | — | **Change this** — Bearer token to protect the bootstrap endpoint |

> **Security:** Set `CORTEX_BOOTSTRAP_ENABLED=false` permanently after initial setup. The bootstrap endpoint self-disables once an organization exists regardless of this flag.

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

## Unified Chat API & Routing Examples

### Authentication

All chat and management endpoints require a valid API key:

```bash
# All requests must include:
-H "Authorization: Bearer cxg_your_api_key_here"
```

### Bootstrap (first-time setup)

```bash
# Create first organization, team, and admin API key
curl -X POST http://localhost:8000/api/v1/bootstrap \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $CORTEX_BOOTSTRAP_TOKEN" \
  -d '{
    "organization_name": "My Company",
    "organization_slug": "my-company",
    "team_name": "Engineering",
    "team_slug": "engineering",
    "admin_key_name": "production-key"
  }'
# Returns the admin API key plaintext — store it securely, shown only once.
```

### `POST /api/v1/chat/completions`

Send a chat request to any provider using the exact same schema.

```bash
# 1. Automatic Multi-Factor Routing (model="auto")
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cxg_your_key" \
  -d '{
    "model": "auto",
    "routing_mode": "auto",
    "messages": [{"role": "user", "content": "Design a resilient microservices architecture."}]
  }'

# 2. Lowest Latency Mode (Selects ultra-fast model e.g. Groq Llama-3.1-8B)
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cxg_your_key" \
  -d '{
    "model": "auto",
    "routing_mode": "lowest_latency",
    "messages": [{"role": "user", "content": "Quick answer: What is the speed of light?"}]
  }'

# 3. Lowest Cost Mode (Prioritizes free self-hosted Ollama models)
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cxg_your_key" \
  -d '{
    "model": "auto",
    "routing_mode": "lowest_cost",
    "messages": [{"role": "user", "content": "Summarize this long document..."}]
  }'

# 4. Capability-Based Routing (Requires Vision capability -> routes to Gemini)
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cxg_your_key" \
  -d '{
    "model": "auto",
    "required_capabilities": ["vision"],
    "messages": [{"role": "user", "content": "Describe what you see in the provided image."}]
  }'

# 5. Direct Manual Routing (Explicit provider & concrete model)
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cxg_your_key" \
  -d '{
    "provider": "ollama",
    "model": "llama3.2",
    "messages": [{"role": "user", "content": "Explain Docker in simple terms."}]
  }'
```

---

### Local Ollama Setup & Model Pulling

To run local models without external API keys:

1. **Install and start Ollama:**
   - Download from [ollama.com](https://ollama.com) or run via Docker Compose (`docker compose up ollama`).
2. **Pull a lightweight model:**
   ```bash
   ollama pull llama3.2
   # or
   ollama pull qwen2.5:0.5b
   ```
3. **Verify installed models dynamically via Cortex Gateway:**
   ```bash
   curl http://localhost:8000/api/v1/providers/ollama/models
   ```

---

**Normalized response (identical shape for all providers, with Phase 4 reliability metadata):**
```json
{
  "id": "ctx_abc123def456",
  "object": "chat.completion",
  "created": 1710000000,
  "provider": "ollama",
  "model": "llama3.2",
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
    "latency_ms": 320.5,
    "routing_mode": "auto",
    "selected_provider": "ollama",
    "selected_model": "llama3.2",
    "original_provider": "groq",
    "failover_triggered": true,
    "retry_count": 1,
    "failover_attempts": 1,
    "circuit_breaker_state": "closed"
  }
}
```

### `GET /api/v1/providers`
```json
{"providers": [{"name": "gemini", "enabled": true, "available": true}, {"name": "groq", "enabled": true, "available": true}, {"name": "ollama", "enabled": true, "available": true}]}
```

### `GET /api/v1/providers/{provider}`
```json
{"name": "ollama", "enabled": true, "available": true, "capabilities": ["chat"]}
```

### `GET /api/v1/providers/{provider}/models`
```json
{"provider": "ollama", "models": ["llama3.2:latest", "qwen2.5:latest"]}
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
| `AUTHENTICATION_FAILED` | 401 | Missing or invalid `cxg_` API key |
| `FORBIDDEN` | 403 | Insufficient role (member vs admin) |
| `BOOTSTRAP_ALREADY_COMPLETED` | 409 | Bootstrap called after org already exists |
| `BOOTSTRAP_DISABLED` | 503 | Bootstrap endpoint is disabled |

Full API docs → http://localhost:8000/docs

---

## Project Structure

```
CortexGateway/
├── backend/
│   ├── alembic/                       # Alembic migration environment
│   │   ├── env.py                     # Async migration runner
│   │   ├── script.py.mako             # Migration file template
│   │   └── versions/
│   │       └── 0001_phase5_auth.py    # organizations, teams, api_keys tables
│   ├── alembic.ini                    # Alembic config
│   ├── app/
│   │   ├── api/v1/endpoints/
│   │   │   ├── health.py              # GET /, /version, /health
│   │   │   ├── chat.py                # POST /api/v1/chat/completions (auth required)
│   │   │   ├── providers.py           # GET /api/v1/providers/*
│   │   │   ├── bootstrap.py           # POST /api/v1/bootstrap (Phase 5)
│   │   │   ├── organizations.py       # Org CRUD (Phase 5)
│   │   │   ├── teams.py               # Team CRUD (Phase 5)
│   │   │   └── api_keys.py            # Key lifecycle (Phase 5)
│   │   ├── auth/                      # Phase 5 — Auth & Multi-Tenancy
│   │   │   ├── dependencies.py        # get_request_context, require_admin
│   │   │   ├── exceptions.py          # AuthenticationError, AuthorizationError
│   │   │   ├── models.py              # Organization, Team, APIKey ORM
│   │   │   ├── schemas.py             # Pydantic schemas + RequestContext ContextVar
│   │   │   ├── security.py            # CSPRNG keygen, HMAC-SHA256, compare_digest
│   │   │   └── service.py             # AuthService DB operations
│   │   ├── config/
│   │   │   └── settings.py            # Pydantic Settings v2 (all phases)
│   │   ├── core/
│   │   │   └── logging.py             # Loguru structured logging
│   │   ├── database/
│   │   │   ├── base.py                # Shared DeclarativeBase for ORM discovery
│   │   │   └── session.py             # SQLAlchemy 2.x async engine + get_db_dependency
│   │   ├── middleware/
│   │   │   ├── request_id.py          # X-Request-ID propagation
│   │   │   └── logging.py             # Request/response logging
│   │   ├── providers/
│   │   │   ├── base.py                # BaseLLMProvider ABC
│   │   │   ├── registry.py            # ProviderRegistry singleton
│   │   │   ├── exceptions.py          # Typed provider exception hierarchy
│   │   │   ├── gemini_provider.py     # Google Gemini async adapter
│   │   │   ├── groq_provider.py       # Groq async adapter
│   │   │   └── ollama_provider.py     # Ollama local async adapter
│   │   ├── routing/                   # Phase 3 — Intelligent Routing Engine
│   │   │   ├── router.py              # RoutingEngine orchestrator
│   │   │   ├── candidates.py          # CandidateBuilder
│   │   │   ├── scorer.py              # CandidateScorer (weighted scoring)
│   │   │   ├── stats.py               # ProviderStatsTracker (rolling metrics)
│   │   │   ├── metadata.py            # ModelMetadataCatalog
│   │   │   ├── policies.py            # RoutingPolicyRegistry (mode weights)
│   │   │   ├── models.py              # RoutingCandidate, RoutingDecision
│   │   │   └── exceptions.py          # Routing-specific exceptions
│   │   ├── reliability/               # Phase 4 — Reliability and Resilience
│   │   │   ├── executor.py            # ReliabilityExecutor (retries, failover)
│   │   │   ├── circuit_breaker.py     # 3-state circuit breaker per provider
│   │   │   ├── retry.py               # Exponential backoff + jitter policy
│   │   │   ├── failover.py            # FailoverSelector (Phase 3 scorer)
│   │   │   ├── errors.py              # Transient/circuit failure classification
│   │   │   └── models.py              # ReliabilityContext, AttemptRecord
│   │   ├── schemas/
│   │   │   ├── responses.py           # Shared Pydantic v2 response models
│   │   │   └── chat.py                # Chat request/response + reliability metadata
│   │   ├── services/
│   │   │   └── chat_service.py        # ChatService — routing + reliability + context
│   │   ├── utils/
│   │   │   └── redis_client.py        # Async Redis client
│   │   ├── exceptions.py              # Global exception handlers
│   │   └── main.py                    # FastAPI app + lifespan
│   ├── tests/
│   │   ├── conftest.py                # Fixtures (DB/Redis mocked)
│   │   ├── test_endpoints.py          # Phase 1 endpoint tests
│   │   ├── test_providers.py          # Phase 2 provider unit tests
│   │   ├── test_chat_api.py           # Phase 2–4 API integration tests
│   │   ├── test_routing.py            # Phase 3 routing engine tests
│   │   ├── test_reliability.py        # Phase 4 reliability tests
│   │   ├── test_auth_security.py      # Phase 5 security unit tests
│   │   ├── test_auth_lifecycle.py     # Phase 5 lifecycle + RBAC tests
│   │   └── test_auth_security_leakage.py  # Phase 5 leakage tests
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pytest.ini
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── api/health.ts              # Type-safe API client
│   │   ├── components/
│   │   │   ├── Layout.tsx             # Sidebar + header shell
│   │   │   └── StatusCard.tsx         # Reusable status card
│   │   └── pages/
│   │       └── Dashboard.tsx          # Live health dashboard
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
| 1 | Infrastructure Foundation | **Done** |
| 2 | Unified Multi-LLM Gateway | **Done** |
| 3 | Intelligent Routing Engine | **Done** |
| 4 | Reliability & Resilience | **Done** |
| 5 | Authentication & Multi-Tenancy | **Done** |
| 6 | Rate Limiting & Budgets | Planned |
| 7 | Cost Tracking & Analytics | Planned |
| 8 | Prometheus & OpenTelemetry | Planned |
| 9 | Admin Dashboard | Planned |

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
