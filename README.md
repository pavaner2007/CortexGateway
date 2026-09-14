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

Cortex Gateway is a centralized AI infrastructure platform designed to give engineering teams complete control over their LLM usage. Instead of each application directly calling OpenAI, Gemini, Groq, or Anthropic, all traffic flows through Cortex Gateway — giving you a single place to manage routing, costs, reliability, rate limits, and compliance.

```
Your Application
      │
      ▼
┌─────────────────────────────────────────────────────┐
│                  Cortex Gateway                      │
│  ┌──────────┐  ┌──────────┐  ┌────────────────┐    │
│  │  Auth    │  │Rate Limit│  │Budget / Cost   │    │
│  └──────────┘  └──────────┘  └────────────────┘    │
│  ┌──────────┐  ┌──────────┐  ┌────────────────┐    │
│  │  Routing │  │Reliability│  │Circuit Breaker │    │
│  └──────────┘  └──────────┘  └────────────────┘    │
└──────┬──────────────┬─────────────────┬─────────────┘
       │              │                 │
       ▼              ▼                 ▼
     Gemini          Groq            Ollama
    (Cloud)        (Cloud)           (Local)
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI · Python 3.12 · Uvicorn |
| **Database** | PostgreSQL 16 · SQLAlchemy 2.x · asyncpg |
| **Cache / Rate Limiting** | Redis 7 · redis-py async · Lua atomic scripts |
| **Config** | Pydantic Settings v2 |
| **Logging** | Loguru |
| **Frontend** | React 18 · TypeScript · Vite · Tailwind CSS |
| **Routing** | React Router v6 |
| **Testing** | pytest · pytest-asyncio · httpx · respx |
| **Containers** | Docker · Docker Compose · Ollama |

---

## Features

### Phase 1 — Infrastructure Foundation ✅
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

### Phase 2 — Unified Multi-LLM Gateway ✅
- **Three active provider adapters** — Google Gemini (Cloud), Groq (Cloud), Ollama (Local / Self-hosted)
- **Provider abstraction** — `BaseLLMProvider` ABC, Open/Closed Principle supporting cloud and local runtimes
- **Provider registry** — register, retrieve, discover providers at runtime
- **Unified chat API** — one endpoint, any provider, normalized response
- **Token usage normalization** — consistent `prompt/completion/total_tokens` across all providers
- **Latency tracking** — provider request duration in every response
- **Error normalization** — 8 typed error codes, correct HTTP status per error type
- **Safe credential handling** — missing keys disable cloud providers gracefully, zero keys needed for Ollama
- **Provider & Model discovery** — list providers, get details, dynamic model discovery (including local Ollama models)

### Phase 3 — Intelligent Routing Engine ✅
- **6 Dynamic Routing Modes**:
  - `auto`: Balanced multi-factor scoring across health (30%), success rate (30%), latency (20%), and cost (20%)
  - `lowest_latency`: Response speed prioritized (60% latency weight)
  - `lowest_cost`: Cost-efficiency prioritized (60% cost weight, prioritizes free self-hosted Ollama)
  - `best_available`: Reliability maximized (80% health + success rate combined)
  - `capability_based`: Strict pre-filtering for required modalities (e.g., `vision`, `json`, `code`)
  - `manual`: Direct bypass with deterministic explicit provider + model targeting
- **Capability Pre-filtering** — Incompatible candidates discarded before scoring
- **Runtime Rolling Statistics** — In-memory tracker for success rates and EMA latency
- **Deterministic Tie-Breaking** — Multi-tiered tie-breaker guarantees repeatable routing decisions
- **Routing Metadata Propagation** — Responses include `routing_mode` for full observability

### Phase 4 — Reliability and Resilience ✅
- **Provider-Specific Timeouts** — Independently configurable per provider
- **Total Request Deadline** — Configurable maximum deadline preventing unbounded retry chains
- **Transient Failure Classification** — Retries only on transient errors; client 4xx fast-fail
- **Exponential Backoff & Jitter** — Non-blocking async sleep with randomized jitter
- **In-Memory Circuit Breaker** — 3-state machine (CLOSED → OPEN → HALF_OPEN) per provider
- **Automated Failover** — Exhausted retries trigger next-best candidate from Phase 3 scorer
- **Capability-Preserving Fallback** — Fallbacks satisfy original request capability constraints
- **Rich Reliability Metadata** — `selected_provider`, `original_provider`, `failover_triggered`, `retry_count`, `circuit_breaker_state`

### Phase 5 — Authentication & Multi-Tenancy ✅
- **API Key Authentication** — Bearer token auth on every protected endpoint (`Authorization: Bearer cxg_...`)
- **CSPRNG key generation** — cryptographically secure, URL-safe keys with `cxg_` prefix
- **HMAC-SHA256 hashing** — server-side pepper + `hmac.compare_digest` constant-time verification (timing-attack resistant)
- **Organizations & Teams** — full tenant hierarchy (1 org → N teams → N API keys)
- **RBAC** — `admin` and `member` roles; admin-only endpoints strictly enforced server-side
- **API Key Lifecycle** — create, list (metadata only), revoke (soft-delete); plaintext shown exactly once
- **Bootstrap endpoint** — `POST /api/v1/bootstrap` creates first org + team + admin key; guarded by `CORTEX_BOOTSTRAP_TOKEN`; auto-disabled after first org exists
- **Cross-tenant isolation** — server enforces org/team ownership; no client-supplied identity trusted
- **Zero key-hash exposure** — `key_hash` never appears in any API response
- **Context propagation** — `RequestContext` (org_id, team_id, key_id, role) flows through every request via ContextVar
- **Alembic migrations** — `organizations`, `teams`, `api_keys` tables with FK cascade

### Phase 6 — Rate Limiting & Budget Management ✅
- **Fixed-Window Rate Limiting** — Redis-backed Lua-atomic counters at three independent scopes: API key, team, organization
- **Atomic Lua Scripts** — single round-trip INCR + EXPIREAT with race-free enforcement; no process-local counters
- **Fail-Open Rate Limiter** — Redis unavailability allows traffic to pass (logged as warning, not a hard failure)
- **429 with Retry-After** — rate-limited responses carry `Retry-After` header indicating exact window reset time
- **Team-Level Budgets** — spending limits with configurable period (daily / weekly / monthly)
- **Three Enforcement Policies**:
  - `BLOCK` — reject request with HTTP 402 when budget would be exceeded
  - `WARN` — allow request but emit structured warning log when threshold crossed
  - `DOWNGRADE` — automatically route to cheapest compatible provider/model within budget using Phase 3 scorer
- **Atomic Budget Reservation** — PostgreSQL `SELECT FOR UPDATE` prevents concurrent overspend; `reserved` column tracks in-flight amounts
- **Lazy Period Rollover** — budget resets on first access after period_end; handled inside the DB lock (no scheduler needed)
- **Split Input/Output Pricing** — `ModelMetadata` extended with `input_cost_per_1k` and `output_cost_per_1k` for accurate per-request cost accounting
- **Estimated vs. Actual Cost** — pre-execution estimate with 1.5× safety margin; reconciled with actual token counts post-execution
- **Budget Reconciliation** — reservation released + actual cost charged after every request; reservation released without charge on provider failure
- **Budget Management API** — `POST/GET/PATCH/DELETE /api/v1/teams/{team_id}/budget` (admin only)
- **Cost & Budget Metadata** — response carries `estimated_cost`, `actual_cost`, `remaining_budget` (optional), `budget_warning`, `budget_downgraded`, `rate_limit_remaining`
- **238 automated tests** — 100% passing across all 6 phases; zero real API credits required

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
# Edit backend/.env — set POSTGRES_PASSWORD, SECRET_KEY, and API_KEY_PEPPER

# 3. Start all services
docker compose up --build
```

That's it. All services start automatically.

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
238 passed in 4.41s
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

### Rate Limiting Configuration (Phase 6)

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_ENABLED` | `true` | Enable Redis-backed rate limiting globally |
| `RATE_LIMIT_API_KEY_REQUESTS` | `100` | Max requests per API key per window |
| `RATE_LIMIT_API_KEY_WINDOW_SECONDS` | `60` | API key window duration in seconds |
| `RATE_LIMIT_TEAM_REQUESTS` | `500` | Max requests per team per window |
| `RATE_LIMIT_TEAM_WINDOW_SECONDS` | `60` | Team window duration in seconds |
| `RATE_LIMIT_ORG_REQUESTS` | `2000` | Max requests per organization per window |
| `RATE_LIMIT_ORG_WINDOW_SECONDS` | `60` | Org window duration in seconds |

### Budget Configuration (Phase 6)

| Variable | Default | Description |
|----------|---------|-------------|
| `BUDGET_ENABLED` | `true` | Enable team-level budget enforcement |
| `BUDGET_DEFAULT_POLICY` | `BLOCK` | Default policy: `BLOCK` \| `WARN` \| `DOWNGRADE` |
| `BUDGET_WARNING_THRESHOLD_PERCENT` | `80` | Log warning when usage reaches this % of limit |
| `BUDGET_EXPOSE_REMAINING` | `false` | Include `remaining_budget` in response metadata |
| `OLLAMA_COST_PER_1K_INPUT_TOKENS` | `0.00` | Ollama input token cost (override for cost accounting) |
| `OLLAMA_COST_PER_1K_OUTPUT_TOKENS` | `0.00` | Ollama output token cost |

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

# 4. Capability-Based Routing (Requires Vision capability → routes to Gemini)
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

**Normalized response (identical shape for all providers, with Phase 6 cost/budget metadata):**
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
    "latency_ms": 320.5,
    "routing_mode": "auto",
    "selected_provider": "groq",
    "selected_model": "llama-3.3-70b-versatile",
    "original_provider": "groq",
    "failover_triggered": false,
    "retry_count": 0,
    "failover_attempts": 0,
    "circuit_breaker_state": "closed",
    "estimated_cost": 0.00001234,
    "actual_cost": 0.00000987,
    "remaining_budget": null,
    "budget_warning": false,
    "budget_downgraded": false,
    "rate_limit_remaining": 99
  }
}
```

---

## Budget Management API

All budget endpoints require an **admin** API key for the team's organization.

### Create a Team Budget

```bash
curl -X POST http://localhost:8000/api/v1/teams/{team_id}/budget \
  -H "Authorization: Bearer cxg_admin_key" \
  -H "Content-Type: application/json" \
  -d '{
    "limit_amount": 50.00,
    "period": "monthly",
    "policy": "BLOCK"
  }'
```

**Policy options:**

| Policy | Behavior |
|--------|----------|
| `BLOCK` | Reject with HTTP 402 when budget would be exceeded |
| `WARN` | Allow request; emit structured warning log when threshold crossed |
| `DOWNGRADE` | Automatically route to cheapest compatible provider within remaining budget |

### Get Team Budget

```bash
curl http://localhost:8000/api/v1/teams/{team_id}/budget \
  -H "Authorization: Bearer cxg_admin_key"
```

```json
{
  "id": "budget-uuid",
  "team_id": "team-uuid",
  "limit_amount": 50.0,
  "current_usage": 12.34,
  "period": "monthly",
  "period_start": "2026-09-01T00:00:00Z",
  "period_end": "2026-10-01T00:00:00Z",
  "policy": "BLOCK",
  "enabled": true,
  "remaining_amount": 37.66,
  "usage_percentage": 24.68,
  "created_at": "2026-09-01T00:00:00Z",
  "updated_at": "2026-09-14T20:00:00Z"
}
```

### Update Budget

```bash
curl -X PATCH http://localhost:8000/api/v1/teams/{team_id}/budget \
  -H "Authorization: Bearer cxg_admin_key" \
  -H "Content-Type: application/json" \
  -d '{"limit_amount": 100.00, "policy": "WARN"}'
```

### Delete Budget

```bash
curl -X DELETE http://localhost:8000/api/v1/teams/{team_id}/budget \
  -H "Authorization: Bearer cxg_admin_key"
# Returns 204 No Content
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

### Error Response Format
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Please retry after the window resets.",
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
| `PROVIDER_RATE_LIMITED` | 429 | Provider upstream rate limit hit |
| `PROVIDER_UNAVAILABLE` | 503 | Provider service down |
| `PROVIDER_AUTHENTICATION_FAILED` | 502 | Invalid/missing API key |
| `PROVIDER_ERROR` | 502 | Generic upstream error |
| `AUTHENTICATION_FAILED` | 401 | Missing or invalid `cxg_` API key |
| `FORBIDDEN` | 403 | Insufficient role (member vs admin) |
| `RATE_LIMIT_EXCEEDED` | 429 | Gateway rate limit hit (key/team/org scope) — includes `Retry-After` header |
| `BUDGET_EXCEEDED` | 402 | Team budget exhausted (BLOCK policy) |
| `BOOTSTRAP_ALREADY_COMPLETED` | 409 | Bootstrap called after org already exists |
| `BOOTSTRAP_DISABLED` | 503 | Bootstrap endpoint is disabled |

Full API docs → http://localhost:8000/docs

---

## Request Pipeline (Phase 6)

Every authenticated request passes through this ordered pipeline:

```
POST /api/v1/chat/completions
        │
        ▼
┌──────────────────────────┐
│  1. Authentication       │  Bearer cxg_... → RequestContext (org/team/key/role)
└──────────┬───────────────┘
           │
        ▼
┌──────────────────────────┐
│  2. Rate Limiting        │  Redis Lua: key-scope + team-scope + org-scope
└──────────┬───────────────┘  → 429 RATE_LIMIT_EXCEEDED if any scope fails
           │
        ▼
┌──────────────────────────┐
│  3. Budget Pre-Check     │  PostgreSQL SELECT FOR UPDATE + estimated_cost
└──────────┬───────────────┘  → 402 BUDGET_EXCEEDED (BLOCK) or downgrade candidate
           │                    selected (DOWNGRADE)
        ▼
┌──────────────────────────┐
│  4. Routing Engine       │  Phase 3: score candidates, apply policy weights
└──────────┬───────────────┘
           │
        ▼
┌──────────────────────────┐
│  5. Reliability Executor │  Phase 4: retries + circuit breaker + failover
└──────────┬───────────────┘
           │
        ▼
┌──────────────────────────┐
│  6. Provider Adapter     │  Gemini / Groq / Ollama
└──────────┬───────────────┘
           │
        ▼
┌──────────────────────────┐
│  7. Actual Cost Calc     │  actual_tokens × split input/output pricing
└──────────┬───────────────┘
           │
        ▼
┌──────────────────────────┐
│  8. Budget Reconcile     │  reserved -= estimated; usage += actual
└──────────┬───────────────┘  (released without charge on provider failure)
           │
        ▼
    ChatCompletionResponse
    (with cost + budget metadata)
```

---

## Project Structure

```
CortexGateway/
├── backend/
│   ├── alembic/                       # Alembic migration environment
│   │   ├── env.py                     # Async migration runner
│   │   ├── script.py.mako             # Migration file template
│   │   └── versions/
│   │       ├── 0001_phase5_auth.py    # organizations, teams, api_keys tables
│   │       └── 0002_phase6_budgets.py # budgets table with reserved column
│   ├── alembic.ini                    # Alembic config
│   ├── app/
│   │   ├── api/v1/endpoints/
│   │   │   ├── health.py              # GET /, /version, /health
│   │   │   ├── chat.py                # POST /api/v1/chat/completions (Phase 2–6)
│   │   │   ├── providers.py           # GET /api/v1/providers/*
│   │   │   ├── bootstrap.py           # POST /api/v1/bootstrap (Phase 5)
│   │   │   ├── organizations.py       # Org CRUD (Phase 5)
│   │   │   ├── teams.py               # Team CRUD (Phase 5)
│   │   │   ├── api_keys.py            # Key lifecycle (Phase 5)
│   │   │   └── budget.py              # Budget CRUD (Phase 6, admin only)
│   │   ├── auth/                      # Phase 5 — Auth & Multi-Tenancy
│   │   │   ├── dependencies.py        # get_request_context, require_admin
│   │   │   ├── exceptions.py          # AuthenticationError, AuthorizationError
│   │   │   ├── models.py              # Organization, Team, APIKey ORM
│   │   │   ├── schemas.py             # Pydantic schemas + RequestContext ContextVar
│   │   │   ├── security.py            # CSPRNG keygen, HMAC-SHA256, compare_digest
│   │   │   └── service.py             # AuthService DB operations
│   │   ├── budget/                    # Phase 6 — Budget Management
│   │   │   ├── cost.py                # CostCalculator (estimate + actual)
│   │   │   ├── exceptions.py          # RateLimitExceeded (429), BudgetExceeded (402)
│   │   │   ├── models.py              # Budget ORM with reserved column
│   │   │   ├── schemas.py             # Pydantic CRUD schemas
│   │   │   └── service.py             # BudgetService (SELECT FOR UPDATE atomicity)
│   │   ├── rate_limit/                # Phase 6 — Rate Limiting
│   │   │   ├── limiter.py             # RateLimiter (Lua atomic fixed-window)
│   │   │   └── models.py              # RateLimitResult, RateLimitOutcome
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
│   │   │   ├── metadata.py            # ModelMetadataCatalog (with split pricing)
│   │   │   ├── policies.py            # RoutingPolicyRegistry (mode weights)
│   │   │   ├── models.py              # ModelMetadata (input/output cost), RoutingDecision
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
│   │   │   └── chat.py                # Chat request/response + Phase 6 cost metadata
│   │   ├── services/
│   │   │   └── chat_service.py        # ChatService — full Phase 1–6 pipeline
│   │   ├── utils/
│   │   │   └── redis_client.py        # Async Redis client
│   │   ├── exceptions.py              # Global exception handlers (incl. 402, 429)
│   │   └── main.py                    # FastAPI app + lifespan
│   ├── tests/
│   │   ├── conftest.py                # Fixtures (DB/Redis mocked)
│   │   ├── test_endpoints.py          # Phase 1 endpoint tests
│   │   ├── test_providers.py          # Phase 2 provider unit tests
│   │   ├── test_chat_api.py           # Phase 2–6 API integration tests
│   │   ├── test_routing.py            # Phase 3 routing engine tests
│   │   ├── test_reliability.py        # Phase 4 reliability tests
│   │   ├── test_auth_security.py      # Phase 5 security unit tests
│   │   ├── test_auth_lifecycle.py     # Phase 5 lifecycle + RBAC tests
│   │   ├── test_auth_security_leakage.py  # Phase 5 leakage tests
│   │   ├── test_rate_limiting.py      # Phase 6 rate limiting tests
│   │   └── test_budget.py             # Phase 6 budget + cost tests
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
| 1 | Infrastructure Foundation | ✅ **Done** |
| 2 | Unified Multi-LLM Gateway | ✅ **Done** |
| 3 | Intelligent Routing Engine | ✅ **Done** |
| 4 | Reliability & Resilience | ✅ **Done** |
| 5 | Authentication & Multi-Tenancy | ✅ **Done** |
| 6 | Rate Limiting & Budget Management | ✅ **Done** |
| 7 | Persistent Usage Analytics | Planned |
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
