<div align="center">

<img src="https://img.shields.io/badge/Cortex-Gateway-6366f1?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiIgZmlsbD0ibm9uZSI+PHJlY3Qgd2lkdGg9IjMyIiBoZWlnaHQ9IjMyIiByeD0iOCIgZmlsbD0iIzYzNjZmMSIvPjxwYXRoIGQ9Ik0xNiA2QzEwLjQ3NyA2IDYgMTAuNDc3IDYgMTZzNC40NzcgMTAgMTAgMTAgMTAtNC40NzcgMTAtMTBTMjEuNTIzIDYgMTYgNnptMCAzYTcgNyAwIDEgMSAwIDE0QTcgNyAwIDAgMSAxNiA5em0wIDJhNC41IDQuNSAwIDEgMCAwIDkgNC41IDQuNSAwIDAgMCAwLTl6bTAgMmEyLjUgMi41IDAgMSAxIDAgNSAyLjUgMi41IDAgMCAxIDAtNXoiIGZpbGw9IndoaXRlIi8+PC9zdmc+" alt="Cortex Gateway" />

# Cortex Gateway

### Intelligent Multi-LLM Gateway and AI Infrastructure Platform

[![Python](https://img.shields.io/badge/Python-3.12+-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61dafb?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178c6?style=flat-square&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7-dc382d?style=flat-square&logo=redis&logoColor=white)](https://redis.io)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ed?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

<br/>

*A production-quality gateway that sits between your applications and multiple LLM providers -- unified routing, health monitoring, failover, rate limiting, cost tracking, and observability.*

</div>

---

## What is Cortex Gateway?

Cortex Gateway is a centralized AI infrastructure platform designed to give engineering teams complete control over their LLM usage. Instead of each application directly calling OpenAI, Gemini, Groq, or Anthropic, all traffic flows through Cortex Gateway -- giving you a single place to manage routing, costs, reliability, rate limits, and compliance.

```
Your Application
      |
      v
+-----------------------------------------------------+
|                  Cortex Gateway                      |
|  +----------+  +----------+  +----------------+    |
|  |  Auth    |  |Rate Limit|  |Budget / Cost   |    |
|  +----------+  +----------+  +----------------+    |
|  +----------+  +----------+  +----------------+    |
|  |  Routing |  |Reliability|  |Circuit Breaker |    |
|  +----------+  +----------+  +----------------+    |
+------+------------------+-----------------+---------+
       |                  |                 |
       v                  v                 v
     Gemini             Groq            Ollama
    (Cloud)           (Cloud)           (Local)
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI , Python 3.12 , Uvicorn |
| **Database** | PostgreSQL 16 , SQLAlchemy 2.x , asyncpg |
| **Cache / Rate Limiting** | Redis 7 , redis-py async , Lua atomic scripts |
| **Config** | Pydantic Settings v2 |
| **Logging** | Loguru |
| **Observability** | Prometheus Client , OpenTelemetry (API/SDK/OTLP) |
| **Frontend** | React 18 , TypeScript , Vite , Tailwind CSS |
| **State Management** | TanStack Query (React Query v5) |
| **Charting** | Recharts |
| **Routing** | React Router v6 |
| **Testing** | pytest , pytest-asyncio , httpx , respx |
| **Containers** | Docker , Docker Compose , Ollama , Prometheus , Grafana |
| **Load Testing** | Locust |
| **Linting / Typing** | ruff , mypy |

---

## Features

### Phase 1 -- Infrastructure Foundation
- **Async FastAPI backend** with full lifespan management
- **PostgreSQL** with SQLAlchemy 2.x async engine and asyncpg driver
- **Redis** async client with connection pooling
- **Health monitoring** -- independent concurrent checks for all dependencies
- **Request ID propagation** -- `X-Request-ID` header through every request
- **Structured logging** -- timestamped, request-scoped, Loguru-powered
- **Global error handling** -- consistent JSON error envelope, no stack traces exposed
- **API documentation** -- Swagger UI at `/docs`, ReDoc at `/redoc`
- **React dashboard** -- live system status with 30s auto-polling
- **Docker Compose** -- full multi-service stack, one command to run

### Phase 2 -- Unified Multi-LLM Gateway
- **Three active provider adapters** -- Google Gemini (Cloud), Groq (Cloud), Ollama (Local / Self-hosted)
- **Provider abstraction** -- `BaseLLMProvider` ABC, Open/Closed Principle supporting cloud and local runtimes
- **Provider registry** -- register, retrieve, discover providers at runtime
- **Unified chat API** -- one endpoint, any provider, normalized response
- **Token usage normalization** -- consistent `prompt/completion/total_tokens` across all providers
- **Latency tracking** -- provider request duration in every response
- **Error normalization** -- 8 typed error codes, correct HTTP status per error type
- **Safe credential handling** -- missing keys disable cloud providers gracefully, zero keys needed for Ollama
- **Provider and Model discovery** -- list providers, get details, dynamic model discovery (including local Ollama models)

### Phase 3 -- Intelligent Routing Engine
- **6 Dynamic Routing Modes**:
  - `auto`: Balanced multi-factor scoring across health (30%), success rate (30%), latency (20%), and cost (20%)
  - `lowest_latency`: Response speed prioritized (60% latency weight)
  - `lowest_cost`: Cost-efficiency prioritized (60% cost weight, prioritizes free self-hosted Ollama)
  - `best_available`: Reliability maximized (80% health + success rate combined)
  - `capability_based`: Strict pre-filtering for required modalities (e.g., `vision`, `json`, `code`)
  - `manual`: Direct bypass with deterministic explicit provider + model targeting
- **Capability Pre-filtering** -- Incompatible candidates discarded before scoring
- **Runtime Rolling Statistics** -- In-memory tracker for success rates and EMA latency
- **Deterministic Tie-Breaking** -- Multi-tiered tie-breaker guarantees repeatable routing decisions
- **Routing Metadata Propagation** -- Responses include `routing_mode` for full observability

### Phase 4 -- Reliability and Resilience
- **Provider-Specific Timeouts** -- Independently configurable per provider
- **Total Request Deadline** -- Configurable maximum deadline preventing unbounded retry chains
- **Transient Failure Classification** -- Retries only on transient errors; client 4xx fast-fail
- **Exponential Backoff and Jitter** -- Non-blocking async sleep with randomized jitter
- **In-Memory Circuit Breaker** -- 3-state machine (CLOSED -> OPEN -> HALF_OPEN) per provider
- **Automated Failover** -- Exhausted retries trigger next-best candidate from Phase 3 scorer
- **Capability-Preserving Fallback** -- Fallbacks satisfy original request capability constraints
- **Rich Reliability Metadata** -- `selected_provider`, `original_provider`, `failover_triggered`, `retry_count`, `circuit_breaker_state`

### Phase 5 -- Authentication and Multi-Tenancy
- **API Key Authentication** -- Bearer token auth on every protected endpoint (`Authorization: Bearer cxg_...`)
- **CSPRNG key generation** -- cryptographically secure, URL-safe keys with `cxg_` prefix
- **HMAC-SHA256 hashing** -- server-side pepper + `hmac.compare_digest` constant-time verification (timing-attack resistant)
- **Organizations and Teams** -- full tenant hierarchy (1 org -> N teams -> N API keys)
- **RBAC** -- `admin` and `member` roles; admin-only endpoints strictly enforced server-side
- **API Key Lifecycle** -- create, list (metadata only), revoke (soft-delete); plaintext shown exactly once
- **Bootstrap endpoint** -- `POST /api/v1/bootstrap` creates first org + team + admin key; guarded by `CORTEX_BOOTSTRAP_TOKEN`; auto-disabled after first org exists
- **Cross-tenant isolation** -- server enforces org/team ownership; no client-supplied identity trusted
- **Zero key-hash exposure** -- `key_hash` never appears in any API response
- **Context propagation** -- `RequestContext` (org_id, team_id, key_id, role) flows through every request via ContextVar
- **Alembic migrations** -- `organizations`, `teams`, `api_keys` tables with FK cascade

### Phase 6 -- Rate Limiting and Budget Management
- **Sliding-Window Rate Limiting** -- Redis-backed Lua-atomic counters at three independent scopes: API key, team, organization; weighted two-window algorithm eliminates the fixed-window 2x boundary burst
- **Per-Team Rate Limit Overrides** -- `POST/GET/DELETE /api/v1/teams/{team_id}/rate-limits` (admin only); per-team rpm/rph overrides stored in DB, fall back to global defaults when unset; DB failure fails open
- **Atomic Lua Scripts** -- single round-trip sliding-window computation (current + previous window weighted by elapsed fraction); race-free enforcement; no process-local counters
- **Fail-Open Rate Limiter** -- Redis or DB unavailability allows traffic to pass (logged as warning, never a hard failure)
- **429 with Retry-After** -- rate-limited responses carry `Retry-After` header indicating exact window reset time
- **Team-Level Budgets** -- spending limits with configurable period (daily / weekly / monthly)
- **Three Enforcement Policies**:
  - `BLOCK` -- reject request with HTTP 402 when budget would be exceeded
  - `WARN` -- allow request but emit structured warning log when threshold crossed
  - `DOWNGRADE` -- automatically route to cheapest compatible provider/model within budget using the routing scorer; capability requirements respected during downgrade; falls back to zero-cost local providers (Ollama) when available; raises 402 if no affordable candidate exists
- **Atomic Budget Reservation** -- PostgreSQL `SELECT FOR UPDATE` prevents concurrent overspend; `reserved` column tracks in-flight amounts
- **Lazy Period Rollover** -- budget resets on first access after period_end; handled inside the DB lock (no scheduler needed)
- **Split Input/Output Pricing** -- `ModelMetadata` extended with `input_cost_per_1k` and `output_cost_per_1k` for accurate per-request cost accounting
- **Estimated vs. Actual Cost** -- pre-execution estimate with 1.5x safety margin; reconciled with actual token counts post-execution
- **Budget Reconciliation** -- reservation released + actual cost charged after every request; reservation released without charge on provider failure
- **Budget Management API** -- `POST/GET/PATCH/DELETE /api/v1/teams/{team_id}/budget` (admin only)
- **Cost and Budget Metadata** -- response carries `estimated_cost`, `actual_cost`, `remaining_budget` (optional), `budget_warning`, `budget_downgraded`, `rate_limit_remaining`

### Phase 7 -- Observability and Analytics
- **Persistent Request Log** -- every request writes one `RequestLog` row to PostgreSQL via a background task using its own dedicated session; observability failures are non-fatal and never affect the chat response
- **9 Prometheus Metrics** -- counters and histograms at `GET /metrics` in standard text exposition format, ready for Prometheus scraping:
  - `gateway_requests_total` (provider, model, status)
  - `gateway_request_latency_seconds` (provider, model)
  - `provider_requests_total` / `provider_errors_total` / `provider_latency_seconds`
  - `fallback_requests_total` (from_provider to to_provider)
  - `circuit_breaker_state` (per provider gauge)
  - `budget_downgrade_total` and `rate_limit_exceeded_total` (scope)
  - Zero high-cardinality labels -- `team_id`, `org_id`, `request_id`, `api_key_id` never appear as Prometheus labels
- **OpenTelemetry Tracing** -- opt-in distributed tracing via OTLP gRPC; disabled by default (`OTEL_ENABLED=false`); gateway operates normally without a collector; `safe_span()` context manager ensures tracing errors are never raised to callers
- **Analytics REST API** -- 7 admin-only endpoints, org-scoped server-side:
  - `GET /api/v1/analytics/requests` -- paginated request log (max 200/page)
  - `GET /api/v1/analytics/costs` -- cost breakdown by provider / model / team
  - `GET /api/v1/analytics/latency` -- avg / p50 / p95 / p99 latency per provider
  - `GET /api/v1/analytics/errors` -- error counts by provider + error_code
  - `GET /api/v1/analytics/fallbacks` -- failover counts by from/to provider
  - `GET /api/v1/analytics/budget-events` -- BLOCK / WARN / DOWNGRADE event counts
  - `GET /api/v1/analytics/timeseries` -- time-bucketed request/cost/error (hour/day/week)
- **Prometheus + Grafana** -- included in Docker Compose; Prometheus scrapes `/metrics` every 15s; Grafana at port 3000 for dashboard creation

### Phase 8 -- Admin Dashboard
- **Single-page React Admin Dashboard** (`frontend/`) -- operator interface for everything built in Phases 1-7
- **Login page** -- validates any API key via `GET /api/v1/auth/me`; only admin keys gain access; key stored securely in `sessionStorage` (cleared on tab close); key never logged, printed, or embedded in URLs
- **Auto 401 redirect** -- any expired session automatically clears state and redirects to `/login`
- **Dashboard** -- live KPI cards (requests, errors, error rate, avg latency, cost); timeseries area chart; cost-by-provider bar chart; configurable time range (24h / 7d / 30d / month); 60-second auto-polling
- **Providers page** -- registered provider list with enabled/available status; last-24h historical traffic metrics (latency, errors, success rate)
- **Teams page** -- org-scoped team list with links to team detail
- **Team Detail page** -- full API key management (create with role, revoke with confirmation dialog; plaintext shown once, then dismissed); budget display and editing with confirmation gate; rate limit display and per-team override editing
- **Budgets page** -- cross-team budget overview with color-coded progress bars (healthy/warning/critical) and policy badges
- **Analytics page** -- full date range selector; requests timeseries; cost chart with provider/model/team groupBy toggle; latency p50/p95/p99 chart; error breakdown table; failover list; budget event list
- **Logs page** -- paginated request log (50/page); status and provider filters persisted in URL params; slide-out detail drawer per request

### Phase 9A -- Model Registry
- **Persistent Model Registry** -- `model_registry` PostgreSQL table replacing the former static catalog; each entry stores provider, model name, split input/output pricing, capability tokens, context window, baseline latency, and enabled flag
- **Admin CRUD API** -- `GET / POST / PATCH / DELETE /api/v1/models` (admin only); all mutations immediately refresh the in-memory catalog singleton
- **DB-Backed Catalog Singleton** -- `_shared_catalog` loaded from the registry at startup and refreshed every 60s via a background task; eliminates hard-coded pricing and capability data from source code
- **Ollama Intersection Logic** -- Ollama model eligibility is enforced as registry intersect installed: models must be both registered in the DB and currently pulled/running in Ollama; unregistered installs and registered-but-missing models are both excluded from routing candidates
- **Bare-Tag Model Matching** -- registry entry `llama3.2` automatically matches live Ollama model `llama3.2:latest` so operators do not need duplicate entries per tag
- **Live Catalog Wiring** -- `RoutingEngine` (Phase 3) and `CostCalculator` (Phase 6) both consume `_shared_catalog` so routing scores and cost estimates always reflect the latest admin configuration without a restart
- **Alembic Migration** -- `0005_phase9a_model_registry.py` creates the table and seeds 15 production-ready model entries (Gemini, Groq, Ollama)

### Phase 9B -- Semantic Caching
- **Redis-Backed Vector Cache** -- embeddings generated at request time; cosine-similarity lookup with configurable threshold (`SEMANTIC_CACHE_SIMILARITY_THRESHOLD`, default 0.92); cache hit returns stored response in under 5ms with no provider call
- **Cache Miss Path** -- on miss the response is written back to Redis in the background (non-blocking) for future hits
- **Team-Scoped Cache Keys** -- cache entries are namespaced per team so different teams never share cached responses
- **Policy-Controlled** -- cache enabled/disabled per team via `CachePolicy` section of the Phase 9C policy engine; global default is disabled
- **Cache Metadata** -- `cache_hit: bool` field on every `ResponseMetadata`; `RequestLog.cache_hit` column persisted for analytics
- **Alembic Migration** -- `0006_phase9b_semantic_cache.py`

### Phase 9C -- Policy Engine
- **Declarative Team Policy** -- single `PUT /api/v1/teams/{team_id}/policy` endpoint (JSON or YAML body) replaces ad-hoc per-team configuration; supports partial overrides (unspecified sections inherit global defaults)
- **Four Policy Sections** -- `routing` (strategy), `fallback` (enabled), `budget` (action: BLOCK/WARN/DOWNGRADE), `cache` (enabled) -- all resolved once per request via `PolicyResolver`
- **Strict Validation** -- Pydantic `extra="forbid"` on all policy schemas; typos like `"routng"` return 422, not silent ignore
- **Global Default Policy** -- `GLOBAL_DEFAULT_POLICY` constant defines gateway-wide fallback; team policy merges on top
- **Fail-Open DB Fallback** -- if the policy DB lookup fails, the request continues with the global default (logged as warning)
- **RBAC Enforced** -- PUT/GET/DELETE all require admin role; org isolation enforced by `_resolve_team`
- **Alembic Migration** -- `0007_phase9c_team_policies.py` (JSONB `policy` column on `team_policies` table)

### Phase 9D -- A/B Testing and Canary
- **Deterministic Traffic Splitting** -- `ExperimentAssigner` uses SHA-256(`team_id:experiment_id:version:request_id`) -> mod 10,000 bucket -> arm; no shared state, no `random.random()`, pure integer arithmetic
- **Two Experiment Types** -- `ab_test` (equal or split traffic) and `canary` (asymmetric e.g. 95/5); same algorithm, different semantics
- **Experiment Configuration via Policy API** -- experiment block added to the existing `PUT /teams/{id}/policy` body; no new endpoint required
- **Strict Schema Validation** -- `sum(weights)==100`, min 2 arms, unique arm names, weight > 0, version >= 1; all enforced at Pydantic schema level
- **Config-Time Provider Validation** -- PUT rejects arms with unregistered providers (HTTP 422 with available providers listed)
- **Pipeline Insertion Point** -- step 2.5 in `ChatService.complete()`: after cache MISS, before budget pre-check; cache hits bypass experiment entirely
- **Arm vs. Actual Provider Distinction** -- `experiment_arm` = assigned arm name (stored before Phase 4 execute); `provider/model` = actual serving provider (may differ on failover)
- **Version-Aware Reshuffling** -- incrementing `experiment.version` changes the hash input and reshuffles traffic distribution
- **Fail-Open Assignment** -- any internal assigner error returns `None` (no assignment); request proceeds with original routing target
- **Full Observability** -- `experiment_id`, `experiment_version`, `experiment_arm` in `ResponseMetadata`, `RequestLog`, and analytics
- **Alembic Migration** -- `0008_phase9d_experiment_log.py` adds 3 nullable columns + index to `request_logs`

### Phase 9E -- Guardrails
- **Prompt Injection Detection** -- regex and heuristic-based scanner blocks jailbreak attempts and instruction-override patterns before the request reaches any provider
- **PII Detection** -- scans prompts for personally identifiable information (emails, phone numbers, SSNs, credit card numbers); configurable to block or redact
- **Prompt Size Enforcement** -- configurable maximum token/character limit per request; prevents runaway cost from oversized prompts
- **Guardrail Runner** -- pluggable pipeline; all guardrails run in sequence; first violation short-circuits with 400 Bad Request and a structured `GuardrailViolation` response
- **Policy-Controlled** -- guardrail settings configurable per team via the Phase 9C policy API; global defaults apply when no team policy is set
- **Fail-Open by Default** -- guardrail evaluation errors are logged and do not block requests
- **Alembic Migration** -- `0009_phase9e_guardrail_log.py` adds guardrail observation columns to `request_logs`

### Phase 10 -- Production Deployment
- **Production Docker Compose** -- `docker-compose.prod.yml`: pre-built images, NGINX reverse proxy, resource limits, `restart: unless-stopped`, required-env validation at startup
- **NGINX Reverse Proxy** -- `nginx/nginx.conf`: security headers (CSP, X-Frame-Options, X-Content-Type-Options), gzip, `server_tokens off`, `proxy_buffering off` for LLM streaming, `/api/*` -> backend, `/` -> frontend static
- **Non-Root Containers** -- backend runs as `appuser` (uid 999); frontend NGINX runs as uid 101; no root processes in production
- **Kubernetes Manifests** -- `k8s/`: namespace, configmap, secret template, backend/frontend deployments (2 replicas), services, NGINX ingress, optional Ollama deployment with GPU annotation
- **Split Health Probes** -- `livenessProbe` uses `GET /version` (process-only); `readinessProbe` uses `GET /health` (full DB + Redis check); avoids restart cascades on transient dependency outage
- **GitHub Actions CI** -- `.github/workflows/ci.yml`: ruff lint, mypy type check, pytest, pip-audit, npm build, npm audit, Docker build verification, gitleaks secret scan
- **Dependency Audit** -- pip-audit and npm audit integrated into CI; findings documented in known-issues when fixes require breaking changes
- **Load Testing** -- `load_tests/locustfile.py`: three Locust user classes (HealthUser, ChatUser, RateLimitUser) configurable via environment variables
- **Authoritative Environment Template** -- `backend/.env.example`: 69 variables covering all phases 1-9E with inline documentation
- **pyproject.toml** -- ruff and mypy configured for the project; 645 style issues auto-fixed (modern Python type annotations, import ordering, deprecated patterns)
- **Deployment Guide** -- `docs/deployment.md`: local development, production Compose, Kubernetes, Alembic migration runbook, Ollama setup, backup/restore, troubleshooting, known limitations
- **Migration Chain Verification** -- discovered and fixed broken Alembic chain (0006 referenced incorrect revision ID for 0005); `alembic history` now walks the complete 9-migration chain cleanly

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
# Edit backend/.env -- set POSTGRES_PASSWORD, SECRET_KEY, and API_KEY_PEPPER

# 3. Start all services
docker compose up --build
```

That's it. All services start automatically.

| Service | URL |
|---------|-----|
| **Admin Dashboard** | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Health Check | http://localhost:8000/health |
| Prometheus Metrics | http://localhost:8000/metrics |
| Prometheus UI | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin / admin) |

> **Admin Dashboard Login**: After bootstrapping (`POST /api/v1/bootstrap`), use the returned admin API key at http://localhost:5173/login. The key is stored securely in `sessionStorage` and never exposed in logs or URLs.

---

## Production Deployment

See [`docs/deployment.md`](docs/deployment.md) for the full guide, including:
- Production Docker Compose (`docker-compose.prod.yml`)
- Kubernetes deployment with `k8s/` manifests
- Alembic migration runbook
- Ollama setup (local host and Kubernetes)
- Backup and restore procedures
- Environment variable reference
- Troubleshooting playbook

Quick production start:

```bash
cp backend/.env.example backend/.env
# Edit .env with real secrets

docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

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

> The backend starts even without PostgreSQL or Redis -- health checks will report `disconnected` until those services are available.

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
372 passed in ~5s
```

No Docker needed -- all external dependencies are mocked.

### Linting and Type Checking

```bash
cd backend
python -m ruff check app/        # lint
python -m ruff check app/ --fix  # auto-fix safe issues
python -m mypy app/ --ignore-missing-imports  # type check
```

### Load Testing

```bash
pip install -r load_tests/requirements.txt

# Web UI at http://localhost:8089
locust -f load_tests/locustfile.py --host http://localhost:8000

# Headless
locust -f load_tests/locustfile.py --host http://localhost:8000 \
  --users 10 --spawn-rate 2 -t 2m --headless --only-summary
```

See [`load_tests/README.md`](load_tests/README.md) for configuration and expected behaviors.

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
| `POSTGRES_PASSWORD` | -- | **Change this** |
| `DATABASE_URL` | *(auto)* | Leave blank -- auto-composed |
| `REDIS_HOST` | `redis` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_URL` | *(auto)* | Leave blank -- auto-composed |
| `SECRET_KEY` | -- | **Change this** (32+ chars) |
| `LOG_LEVEL` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |

### Provider Configuration (Phase 2)

| Variable | Default | Description |
|----------|---------|-------------|
| `PROVIDER_TIMEOUT_SECONDS` | `30` | Timeout for all provider requests |
| `DEFAULT_PROVIDER` | -- | Optional default provider name |
| `DEFAULT_MODEL` | -- | Optional default model |
| `GEMINI_API_KEY` | -- | Google Gemini API key (blank = disabled) |
| `GEMINI_ENABLED` | `true` | Enable/disable Gemini |
| `GEMINI_TIMEOUT_SECONDS` | `30` | Gemini-specific request timeout |
| `GROQ_API_KEY` | -- | Groq API key (blank = disabled) |
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
| `API_KEY_PEPPER` | -- | **Change this** -- HMAC-SHA256 pepper for key hashing. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `CORTEX_BOOTSTRAP_ENABLED` | `true` | Enable bootstrap endpoint. Set to `false` after first org is created |
| `CORTEX_BOOTSTRAP_TOKEN` | -- | **Change this** -- Bearer token to protect the bootstrap endpoint |

> **Security:** Set `CORTEX_BOOTSTRAP_ENABLED=false` permanently after initial setup. The bootstrap endpoint self-disables once an organization exists regardless of this flag.

### Rate Limiting Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_ENABLED` | `true` | Enable Redis-backed rate limiting globally |
| `RATE_LIMIT_API_KEY_REQUESTS` | `100` | Global max requests per API key per 60s window |
| `RATE_LIMIT_API_KEY_WINDOW_SECONDS` | `60` | API key window duration in seconds |
| `RATE_LIMIT_TEAM_REQUESTS` | `500` | Global max requests per team per 60s window (overridable per-team via API) |
| `RATE_LIMIT_TEAM_WINDOW_SECONDS` | `60` | Team window duration in seconds |
| `RATE_LIMIT_ORG_REQUESTS` | `2000` | Max requests per organization per window |
| `RATE_LIMIT_ORG_WINDOW_SECONDS` | `60` | Org window duration in seconds |

> **Per-team overrides:** Use `POST /api/v1/teams/{team_id}/rate-limits` to give individual teams different limits. The global env vars above serve as the default for teams without a configured override.

### Budget Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `BUDGET_ENABLED` | `true` | Enable team-level budget enforcement |
| `BUDGET_DEFAULT_POLICY` | `BLOCK` | Default policy: `BLOCK` \| `WARN` \| `DOWNGRADE` |
| `BUDGET_WARNING_THRESHOLD_PERCENT` | `80` | Log warning when usage reaches this % of limit |
| `BUDGET_EXPOSE_REMAINING` | `false` | Include `remaining_budget` in response metadata |
| `OLLAMA_COST_PER_1K_INPUT_TOKENS` | `0.00` | Ollama input token cost (override for cost accounting) |
| `OLLAMA_COST_PER_1K_OUTPUT_TOKENS` | `0.00` | Ollama output token cost |

### Observability Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `METRICS_ENABLED` | `true` | Expose `GET /metrics` in Prometheus text format |
| `OTEL_ENABLED` | `false` | Enable OpenTelemetry distributed tracing |
| `OTEL_SERVICE_NAME` | `cortex-gateway` | Service name reported to the OTel collector |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | -- | gRPC collector endpoint, e.g. `http://otel-collector:4317` |
| `REQUEST_LOG_ENABLED` | `true` | Persist one `RequestLog` row per request to PostgreSQL |

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

## Unified Chat API and Routing Examples

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
# Returns the admin API key plaintext -- store it securely, shown only once.
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

# 2. Lowest Latency Mode
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

# 4. Capability-Based Routing (Requires Vision capability)
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cxg_your_key" \
  -d '{
    "model": "auto",
    "required_capabilities": ["vision"],
    "messages": [{"role": "user", "content": "Describe what you see in the provided image."}]
  }'

# 5. Direct Manual Routing (Explicit provider and concrete model)
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cxg_your_key" \
  -d '{
    "provider": "ollama",
    "model": "llama3.2",
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
    "rate_limit_remaining": 99,
    "cache_hit": false
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
| `DOWNGRADE` | Re-route to cheapest compatible provider/model within remaining budget; capability constraints respected; Ollama (zero-cost) preferred as fallback; raises 402 if no affordable candidate exists |

### Get Team Budget

```bash
curl http://localhost:8000/api/v1/teams/{team_id}/budget \
  -H "Authorization: Bearer cxg_admin_key"
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

## Per-Team Rate Limit Management API

All rate limit endpoints require an **admin** API key. Per-team limits override the global defaults for that team only; all other teams continue using the global env var defaults.

### View Effective Rate Limits

```bash
curl http://localhost:8000/api/v1/teams/{team_id}/rate-limits \
  -H "Authorization: Bearer cxg_admin_key"
```

### Set Per-Team Rate Limits

```bash
curl -X POST http://localhost:8000/api/v1/teams/{team_id}/rate-limits \
  -H "Authorization: Bearer cxg_admin_key" \
  -H "Content-Type: application/json" \
  -d '{
    "requests_per_minute": 200,
    "requests_per_hour": 3000
  }'
# Pass null for a field to revert it to the global default
```

### Remove Team Rate Limit Overrides

```bash
curl -X DELETE http://localhost:8000/api/v1/teams/{team_id}/rate-limits \
  -H "Authorization: Bearer cxg_admin_key"
# Returns 204 -- team reverts to global defaults
```

---

## Model Registry API (Phase 9A)

All model registry endpoints require an **admin** API key. The registry is the single source of truth for model metadata -- pricing, capabilities, context window, and routing eligibility.

### List All Models

```bash
curl http://localhost:8000/api/v1/models \
  -H "Authorization: Bearer cxg_admin_key"
```

### Add a New Model

```bash
curl -X POST http://localhost:8000/api/v1/models \
  -H "Authorization: Bearer cxg_admin_key" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "groq",
    "model_name": "llama-3.3-70b-versatile",
    "input_cost_per_1k": 0.00059,
    "output_cost_per_1k": 0.00079,
    "capabilities": ["text", "json", "code", "tools"],
    "context_window": 128000,
    "baseline_latency_ms": 180.0,
    "enabled": true
  }'
```

**Supported capability tokens:** `text`, `vision`, `json`, `code`, `tools`, `function_calling`, `complex_reasoning`

### Update a Model

```bash
curl -X PATCH http://localhost:8000/api/v1/models/{model_id} \
  -H "Authorization: Bearer cxg_admin_key" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

Changes take effect immediately -- the in-memory routing catalog is refreshed within milliseconds.

### Delete a Model

```bash
curl -X DELETE http://localhost:8000/api/v1/models/{model_id} \
  -H "Authorization: Bearer cxg_admin_key"
# Returns 204 No Content
```

---

## Local Ollama Setup

To run local models without external API keys:

1. **Install and start Ollama:**
   - Download from [ollama.com](https://ollama.com) or run via Docker Compose (`docker compose up ollama`).
2. **Pull a lightweight model:**
   ```bash
   ollama pull llama3.2
   # or
   ollama pull qwen2.5:0.5b
   ```
3. **Verify installed models via Cortex Gateway:**
   ```bash
   curl http://localhost:8000/api/v1/providers/ollama/models
   ```

---

## Error Response Format

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
| `RATE_LIMIT_EXCEEDED` | 429 | Gateway rate limit hit (key/team/org scope) -- includes `Retry-After` header |
| `BUDGET_EXCEEDED` | 402 | Team budget exhausted (BLOCK policy) |
| `GUARDRAIL_VIOLATION` | 400 | Request blocked by guardrail (Phase 9E) |
| `BOOTSTRAP_ALREADY_COMPLETED` | 409 | Bootstrap called after org already exists |
| `BOOTSTRAP_DISABLED` | 503 | Bootstrap endpoint is disabled |

Full API docs: http://localhost:8000/docs

---

## Request Pipeline

Every authenticated request passes through this ordered pipeline:

```
POST /api/v1/chat/completions
        |
        v
+--------------------------+
|  0. Policy Resolution    |  PolicyResolver -> ResolvedPolicy (routing/fallback/budget/cache/experiment)
+--------------------------+  DB lookup once per request; fail-open to global default
           |
        v
+--------------------------+
|  1. Authentication       |  Bearer cxg_... -> RequestContext (org/team/key/role)
+--------------------------+
           |
        v
+--------------------------+
|  2. Rate Limiting        |  Redis Lua: key-scope + team-scope + org-scope
+--------------------------+  -> 429 RATE_LIMIT_EXCEEDED if any scope fails
           |
        v
+--------------------------+
|  3. Guardrails           |  Injection / PII / prompt-size checks (Phase 9E)
+--------------------------+  -> 400 GUARDRAIL_VIOLATION on first failure
           |
        v
+--------------------------+
|  4. Routing Engine       |  Multi-factor scoring -> initial target_provider/model
+--------------------------+
           |
        v
+--------------------------+
|  5. Semantic Cache       |  Redis vector similarity lookup (Phase 9B)
+--------------------------+  HIT -> return immediately (no experiment, no budget)
           | MISS
        v
+--------------------------+
|  6. Experiment Assign    |  SHA-256 hash -> bucket -> arm -> override provider/model (Phase 9D)
+--------------------------+  Disabled/absent experiment -> skip
           |
        v
+--------------------------+
|  7. Budget Pre-Check     |  PostgreSQL SELECT FOR UPDATE + estimated_cost
+--------------------------+  -> 402 BUDGET_EXCEEDED (BLOCK) or downgrade (DOWNGRADE)
           |
        v
+--------------------------+
|  8. Reliability Executor |  Retries + circuit breaker + automated failover
+--------------------------+
           |
        v
+--------------------------+
|  9. Provider Adapter     |  Gemini / Groq / Ollama
+--------------------------+
           |
        v
+--------------------------+
|  10. Actual Cost Calc    |  actual_tokens x split input/output pricing
+--------------------------+
           |
        v
+--------------------------+
|  11. Budget Reconcile    |  reserved -= estimated; usage += actual
+--------------------------+  (released without charge on provider failure)
           |
        v
    ChatCompletionResponse
    (cost + budget + cache + experiment + guardrail metadata)
           |
        v  [Background -- non-blocking]
+--------------------------+
|  12. Observability       |  RequestLog row -> PostgreSQL (own session)
+--------------------------+  Prometheus counters incremented
                              OTel span closed (if enabled)
                              Cache write (on miss, Phase 9B)
```

---

## Project Structure

```
CortexGateway/
+-- .github/
|   +-- workflows/
|       +-- ci.yml                         # GitHub Actions CI pipeline
+-- backend/
|   +-- alembic/                           # Alembic migration environment
|   |   +-- env.py                         # Async migration runner
|   |   +-- script.py.mako                 # Migration file template
|   |   +-- versions/
|   |       +-- 0001_phase5_auth.py        # organizations, teams, api_keys tables
|   |       +-- 0002_phase6_budgets.py     # budgets table with reserved column
|   |       +-- 0003_phase6_team_rate_limits.py  # per-team rate limit overrides
|   |       +-- 0004_phase7_request_logs.py      # request_logs table (observability)
|   |       +-- 0005_phase9a_model_registry.py   # model_registry table + 15 seed entries
|   |       +-- 0006_phase9b_semantic_cache.py   # cache_hit column on request_logs
|   |       +-- 0007_phase9c_team_policies.py    # team_policies table (JSONB policy)
|   |       +-- 0008_phase9d_experiment_log.py   # experiment columns on request_logs
|   |       +-- 0009_phase9e_guardrail_log.py    # guardrail observation columns
|   +-- alembic.ini                        # Alembic config
|   +-- pyproject.toml                     # ruff + mypy + pytest configuration
|   +-- app/
|   |   +-- api/v1/endpoints/
|   |   |   +-- health.py                  # GET /, /version, /health
|   |   |   +-- chat.py                    # POST /api/v1/chat/completions
|   |   |   +-- providers.py               # GET /api/v1/providers/*
|   |   |   +-- bootstrap.py               # POST /api/v1/bootstrap
|   |   |   +-- organizations.py           # Org CRUD (admin only)
|   |   |   +-- teams.py                   # Team CRUD (admin only)
|   |   |   +-- api_keys.py                # Key lifecycle (admin only)
|   |   |   +-- budget.py                  # Budget CRUD (admin only)
|   |   |   +-- rate_limits.py             # Per-team rate limit overrides (admin only)
|   |   |   +-- analytics.py               # GET /api/v1/analytics/* (admin only)
|   |   |   +-- model_registry.py          # GET/POST/PATCH/DELETE /api/v1/models (Phase 9A)
|   |   |   +-- policy.py                  # GET/PUT/DELETE /api/v1/teams/{id}/policy (Phase 9C)
|   |   |   +-- metrics.py                 # GET /metrics (Prometheus exposition)
|   |   +-- auth/                          # Authentication and Multi-Tenancy
|   |   |   +-- dependencies.py
|   |   |   +-- models.py
|   |   |   +-- schemas.py
|   |   |   +-- security.py
|   |   |   +-- service.py
|   |   +-- budget/                        # Budget Management
|   |   |   +-- cost.py
|   |   |   +-- exceptions.py
|   |   |   +-- models.py
|   |   |   +-- schemas.py
|   |   |   +-- service.py
|   |   +-- rate_limit/                    # Rate Limiting
|   |   |   +-- limiter.py
|   |   |   +-- team_limits.py
|   |   |   +-- models.py
|   |   +-- guardrails/                    # Phase 9E -- Guardrails
|   |   |   +-- base.py
|   |   |   +-- injection.py
|   |   |   +-- pii.py
|   |   |   +-- prompt_size.py
|   |   |   +-- runner.py
|   |   |   +-- exceptions.py
|   |   +-- experiment/                    # Phase 9D -- A/B Testing and Canary
|   |   |   +-- assigner.py
|   |   |   +-- schemas.py
|   |   +-- policy/                        # Phase 9C -- Policy Engine
|   |   |   +-- schemas.py
|   |   |   +-- resolver.py
|   |   |   +-- service.py
|   |   |   +-- models.py
|   |   +-- semantic_cache/                # Phase 9B -- Semantic Caching
|   |   |   +-- cache.py
|   |   +-- model_registry/                # Phase 9A -- Model Registry
|   |   |   +-- models.py
|   |   |   +-- schemas.py
|   |   |   +-- service.py
|   |   |   +-- exceptions.py
|   |   +-- config/
|   |   |   +-- settings.py
|   |   +-- database/
|   |   |   +-- base.py
|   |   |   +-- session.py
|   |   +-- providers/
|   |   |   +-- base.py
|   |   |   +-- registry.py
|   |   |   +-- exceptions.py
|   |   |   +-- gemini_provider.py
|   |   |   +-- groq_provider.py
|   |   |   +-- ollama_provider.py
|   |   +-- routing/                       # Phase 3 -- Intelligent Routing Engine
|   |   |   +-- router.py
|   |   |   +-- candidates.py
|   |   |   +-- scorer.py
|   |   |   +-- stats.py
|   |   |   +-- metadata.py
|   |   |   +-- policies.py
|   |   |   +-- models.py
|   |   |   +-- exceptions.py
|   |   +-- reliability/                   # Phase 4 -- Reliability and Resilience
|   |   |   +-- executor.py
|   |   |   +-- circuit_breaker.py
|   |   |   +-- retry.py
|   |   |   +-- failover.py
|   |   |   +-- models.py
|   |   +-- observability/                 # Phase 7 -- Observability
|   |   |   +-- models.py
|   |   |   +-- metrics.py
|   |   |   +-- tracing.py
|   |   |   +-- log_writer.py
|   |   |   +-- analytics_schemas.py
|   |   |   +-- analytics_service.py
|   |   +-- schemas/
|   |   |   +-- responses.py
|   |   |   +-- chat.py
|   |   +-- services/
|   |   |   +-- chat_service.py            # Full request pipeline (Phases 1-9E)
|   |   +-- middleware/
|   |   |   +-- request_id.py
|   |   |   +-- logging.py
|   |   +-- utils/
|   |   |   +-- redis_client.py
|   |   +-- exceptions.py
|   |   +-- main.py                        # FastAPI app + lifespan
|   +-- tests/
|   |   +-- conftest.py
|   |   +-- test_endpoints.py
|   |   +-- test_providers.py
|   |   +-- test_chat_api.py
|   |   +-- test_routing.py
|   |   +-- test_reliability.py
|   |   +-- test_auth_security.py
|   |   +-- test_auth_lifecycle.py
|   |   +-- test_auth_security_leakage.py
|   |   +-- test_rate_limiting.py
|   |   +-- test_budget.py
|   |   +-- test_team_rate_limits.py
|   |   +-- test_observability.py
|   |   +-- test_phase8_backend.py
|   |   +-- test_phase9a_model_registry.py
|   |   +-- test_phase9b_semantic_cache.py
|   |   +-- test_phase9c_policy.py
|   |   +-- test_phase9d_experiment.py
|   |   +-- test_phase9e_guardrails.py
|   +-- Dockerfile
|   +-- requirements.txt
|   +-- pytest.ini
|   +-- .env.example
|
+-- frontend/
|   +-- src/
|   |   +-- api/
|   |   +-- components/
|   |   +-- pages/
|   +-- Dockerfile
|   +-- nginx.conf
|   +-- package.json
|   +-- vite.config.ts
|
+-- nginx/
|   +-- nginx.conf                         # Production reverse proxy
|
+-- k8s/
|   +-- namespace.yaml
|   +-- configmap.yaml
|   +-- secret.yaml                        # Template -- do not commit real values
|   +-- backend-deployment.yaml
|   +-- backend-service.yaml
|   +-- frontend-deployment.yaml
|   +-- ingress.yaml
|   +-- ollama-deployment.yaml             # Optional, GPU-annotated
|   +-- README.md
|
+-- load_tests/
|   +-- locustfile.py                      # Locust scenarios (health, chat, rate-limit)
|   +-- requirements.txt                   # pip install -r load_tests/requirements.txt
|   +-- README.md
|
+-- observability/
|   +-- prometheus.yml                     # Prometheus scrape config
|
+-- docs/
|   +-- architecture.md
|   +-- deployment.md                      # Full production deployment guide
|
+-- docker-compose.yml                     # Development stack
+-- docker-compose.prod.yml                # Production stack
+-- README.md
```

---

## Roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | Infrastructure Foundation | Done |
| 2 | Unified Multi-LLM Gateway | Done |
| 3 | Intelligent Routing Engine | Done |
| 4 | Reliability and Resilience | Done |
| 5 | Authentication and Multi-Tenancy | Done |
| 6 | Rate Limiting and Budget Management | Done |
| 7 | Observability and Analytics | Done |
| 8 | Admin Dashboard | Done |
| 9A | Model Registry | Done |
| 9B | Semantic Caching | Done |
| 9C | Policy Engine | Done |
| 9D | A/B Testing and Canary | Done |
| 9E | Guardrails | Done |
| 10 | Production Deployment | Done |

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

MIT 2026 [Cortex Gateway Contributors](LICENSE)
