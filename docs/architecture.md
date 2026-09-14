# Cortex Gateway — Architecture Reference (Phases 1–6)

## Overview

Cortex Gateway is a production-quality Multi-LLM Gateway built across six progressive phases:

| Phase | Name | Key Concern |
|-------|------|-------------|
| 1 | Infrastructure Foundation | PostgreSQL, Redis, async FastAPI, health checks |
| 2 | Unified Multi-LLM Gateway | Provider adapters, normalized API |
| 3 | Intelligent Routing Engine | Multi-mode scoring, capability pre-filtering |
| 4 | Reliability & Resilience | Circuit breakers, retries, automatic failover |
| 5 | Authentication & Multi-Tenancy | API keys, RBAC, orgs, teams |
| 6 | Rate Limiting & Budget Management | Redis counters, budget reservation, cost tracking |

---

## Full Request Pipeline (Phase 6)

Every request to `POST /api/v1/chat/completions` traverses this ordered pipeline:

```
Client
  │  Authorization: Bearer cxg_...
  ▼
┌─────────────────────────────────────────────────────────────────┐
│  ASGI Middleware Stack                                           │
│  1. CORSMiddleware                                               │
│  2. RequestIDMiddleware  (X-Request-ID: <uuid>)                 │
│  3. RequestLoggingMiddleware                                      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 5 — Authentication                                        │
│  get_request_context()                                           │
│  • Reads Bearer token from Authorization header                  │
│  • Looks up key_hash in api_keys table                          │
│  • Validates HMAC-SHA256 with pepper                            │
│  • Checks expiry, revocation                                     │
│  • Returns RequestContext(org_id, team_id, key_id, role)        │
│  → 401 AUTHENTICATION_FAILED on any failure                     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 6 — Rate Limiting                                         │
│  RateLimiter.check_all()                                         │
│  • Checks 3 independent fixed-window counters via Lua script:   │
│    ratelimit:key:<api_key_id>:<window_start>                    │
│    ratelimit:team:<team_id>:<window_start>                      │
│    ratelimit:org:<org_id>:<window_start>                        │
│  • All counters incremented atomically (INCR + EXPIREAT)        │
│  • Fails open if Redis is unavailable                           │
│  → 429 RATE_LIMIT_EXCEEDED + Retry-After header                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 3 — Routing Engine                                        │
│  RoutingEngine.route()                                           │
│  • Resolves routing mode (manual / auto / lowest_cost / etc.)   │
│  • CandidateBuilder.build_candidates() — active providers       │
│  • Capability pre-filter (vision, json, code, tools)            │
│  • Health filter                                                 │
│  • CandidateScorer — weighted scoring (health/success/lat/cost) │
│  → RoutingDecision(provider, model, score)                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 6 — Budget Pre-Check & Reservation                        │
│  BudgetService.check_and_reserve()                               │
│  • CostCalculator.estimate_cost() — input chars/4 + max_tokens  │
│    × 1.5 safety margin × split input/output pricing             │
│  • SELECT FOR UPDATE locks budget row (prevents overspend)      │
│  • Lazy rollover if period_end < utcnow (resets inside lock)    │
│  BLOCK  → 402 BUDGET_EXCEEDED if usage+reserved+est > limit     │
│  WARN   → allow; log warning if threshold crossed                │
│  DOWNGRADE → score affordable candidates; pick cheapest via     │
│    Phase 3 CandidateScorer; → 402 if none found                 │
│  • budget.reserved += estimated_cost (in-flight reservation)    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 4 — Reliability Executor                                  │
│  ReliabilityExecutor.execute()                                   │
│  • Enforces total request deadline                               │
│  • Per-provider retry loop with exponential backoff + jitter    │
│  • CircuitBreaker per provider (CLOSED → OPEN → HALF_OPEN)      │
│  • FailoverSelector: Phase 3 scorer over remaining candidates   │
│  • Preserves original capability constraints during failover     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2 — Provider Adapter                                      │
│  BaseLLMProvider.chat()                                          │
│  • GeminiProvider / GroqProvider / OllamaProvider               │
│  • Normalizes request → provider SDK format                     │
│  • Normalizes response → ChatCompletionResponse                 │
│  • Normalizes token usage (prompt/completion/total)             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 6 — Actual Cost Calculation & Reconciliation             │
│  CostCalculator.calculate_actual_cost()                          │
│  • Uses provider-returned prompt_tokens + completion_tokens      │
│  • actual = (prompt/1000 × input_cost_per_1k)                   │
│           + (completion/1000 × output_cost_per_1k)              │
│  • Falls back to estimated_cost if usage is None                │
│                                                                   │
│  BudgetService.reconcile()                                       │
│  • reserved -= estimated_cost                                    │
│  • current_usage += actual_cost                                  │
│  On provider failure: release_reservation() (no charge)         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
              ChatCompletionResponse
         (with cost, budget, rate-limit metadata)
```

---

## High-Level System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         Client Browser                            │
└────────────────────────┬─────────────────────────────────────────┘
                         │ HTTP (port 5173)
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│              React Frontend (Vite + Tailwind)                     │
│   Dashboard → Live health status with 30s auto-polling            │
└────────────────────────┬─────────────────────────────────────────┘
                         │ HTTP (port 8000)
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                   FastAPI Backend                                  │
│                                                                    │
│  Auth (P5) → Rate Limit (P6) → Routing (P3) → Budget (P6)        │
│  → Reliability (P4) → Provider (P2) → Cost Reconcile (P6)        │
│                                                                    │
└──────┬──────────────────────┬───────────────────────┬────────────┘
       │                      │                       │
       ▼                      ▼                       ▼
┌─────────────────┐  ┌────────────────────┐  ┌────────────────────┐
│   PostgreSQL 16  │  │     Redis 7         │  │  LLM Providers     │
│   (asyncpg)      │  │  (Lua rate limits)  │  │  Gemini / Groq /   │
│  - organizations │  │  Fixed-window       │  │  Ollama            │
│  - teams         │  │  counters:          │  └────────────────────┘
│  - api_keys      │  │  key / team / org   │
│  - budgets       │  └────────────────────┘
└─────────────────┘
```

---

## Backend Module Architecture

```
backend/app/
│
├── config/
│   └── settings.py          Pydantic Settings v2
│                            - Loads from .env / environment variables
│                            - Single lru_cache singleton
│                            - Phase 6: rate limit + budget + Ollama pricing vars
│
├── core/
│   └── logging.py           Loguru structured logging
│                            - Single stderr sink, no stack traces
│
├── database/
│   ├── base.py              Shared DeclarativeBase
│   └── session.py           SQLAlchemy 2.x async engine + get_db_dependency
│
├── utils/
│   └── redis_client.py      Async Redis client
│                            - init_redis() / close_redis() lifecycle
│                            - Shared by rate limiter and health checks
│
├── middleware/
│   ├── request_id.py        X-Request-ID propagation (ContextVar)
│   └── logging.py           Request/response structured log line
│
├── schemas/
│   ├── responses.py         Shared Pydantic v2 response models
│   └── chat.py              ChatCompletionRequest, ChatCompletionResponse
│                            ResponseMetadata (incl. Phase 6 cost/budget fields)
│
├── auth/                    Phase 5 — Authentication & Multi-Tenancy
│   ├── dependencies.py      get_request_context, require_admin (FastAPI deps)
│   ├── exceptions.py        AuthenticationError (401), AuthorizationError (403)
│   ├── models.py            Organization, Team, APIKey ORM models
│   ├── schemas.py           Pydantic schemas + RequestContext dataclass
│   ├── security.py          CSPRNG keygen, HMAC-SHA256, compare_digest
│   └── service.py           AuthService.authenticate() — DB lookup + verify
│
├── rate_limit/              Phase 6 — Rate Limiting
│   ├── limiter.py           RateLimiter
│   │                        - Fixed-window via Redis Lua script
│   │                        - Atomic INCR + EXPIREAT in single round-trip
│   │                        - Checks 3 scopes: api_key, team, org
│   │                        - Fail-open when Redis is unavailable
│   └── models.py            RateLimitResult, RateLimitOutcome dataclasses
│
├── budget/                  Phase 6 — Budget Management
│   ├── cost.py              CostCalculator
│   │                        - estimate_cost(): chars/4 → tokens × pricing × 1.5×
│   │                        - calculate_actual_cost(): real tokens × split pricing
│   │                        - Fallback to estimate if usage is None
│   ├── exceptions.py        RateLimitExceeded (429), BudgetExceeded (402)
│   ├── models.py            Budget ORM
│   │                        - reserved column for concurrent pre-reservation
│   │                        - period_start/period_end for lazy rollover
│   │                        - policy: BLOCK | WARN | DOWNGRADE
│   ├── schemas.py           BudgetCreate, BudgetUpdate, BudgetResponse
│   └── service.py           BudgetService
│                            - check_and_reserve(): SELECT FOR UPDATE
│                            - _apply_rollover_if_needed(): inside lock
│                            - reconcile(): release reservation + charge actual
│                            - release_reservation(): no charge on failure
│
├── providers/               Phase 2 — Provider Adapters
│   ├── base.py              BaseLLMProvider ABC
│   ├── registry.py          ProviderRegistry singleton + get_registry() dep
│   ├── exceptions.py        Typed exception hierarchy (8 types)
│   ├── gemini_provider.py   Google Gemini adapter
│   ├── groq_provider.py     Groq adapter (OpenAI-compatible)
│   └── ollama_provider.py   Ollama local adapter
│
├── routing/                 Phase 3 — Intelligent Routing Engine
│   ├── router.py            RoutingEngine.route() — mode resolution + orchestration
│   ├── candidates.py        CandidateBuilder — live candidate discovery
│   ├── scorer.py            CandidateScorer — normalized weighted scoring
│   │                        Factors: health, success_rate, latency, cost
│   ├── stats.py             ProviderStatsTracker — rolling success rate + EMA latency
│   ├── metadata.py          ModelMetadataCatalog
│   │                        - cost_per_1k_tokens (Phase 3 scoring)
│   │                        - input_cost_per_1k / output_cost_per_1k (Phase 6 billing)
│   ├── policies.py          RoutingPolicyRegistry — per-mode weight presets
│   ├── models.py            ModelMetadata, RoutingCandidate, RoutingDecision
│   └── exceptions.py        Routing-specific exceptions
│
├── reliability/             Phase 4 — Reliability & Resilience
│   ├── executor.py          ReliabilityExecutor.execute()
│   │                        - Deadline enforcement
│   │                        - Retry loop with per-provider circuit breaker
│   │                        - Failover to next-best candidate on exhaustion
│   ├── circuit_breaker.py   CircuitBreaker (CLOSED / OPEN / HALF_OPEN)
│   │                        - Async lock protection on state transitions
│   ├── retry.py             ExponentialBackoffPolicy
│   ├── failover.py          FailoverSelector (Phase 3 scorer, loop prevention)
│   ├── errors.py            Transient vs. permanent failure classification
│   └── models.py            ReliabilityContext, AttemptRecord
│
├── services/
│   └── chat_service.py      ChatService.complete()
│                            Full Phase 1–6 orchestration:
│                            Rate limit → Budget reserve → Routing →
│                            Reliability → Provider → Cost calc → Reconcile
│
├── api/v1/endpoints/
│   ├── health.py            GET / /version /health
│   ├── chat.py              POST /api/v1/chat/completions
│   │                        Injects: auth, rate_limiter, budget_service, cost_calculator
│   ├── providers.py         GET /api/v1/providers/*
│   ├── bootstrap.py         POST /api/v1/bootstrap (Phase 5)
│   ├── organizations.py     Org CRUD (Phase 5, admin)
│   ├── teams.py             Team CRUD (Phase 5, admin)
│   ├── api_keys.py          Key lifecycle (Phase 5, admin)
│   └── budget.py            Budget CRUD (Phase 6, admin)
│                            POST/GET/PATCH/DELETE /api/v1/teams/{team_id}/budget
│
├── exceptions.py            Global exception handlers
│                            - 422 RequestValidationError
│                            - 401 AuthenticationError
│                            - 403 AuthorizationError
│                            - 429 RateLimitExceeded + Retry-After header
│                            - 402 BudgetExceeded
│                            - Provider exceptions → correct HTTP status
│                            - 500 catch-all (no internal details exposed)
│
└── main.py                  FastAPI app + lifespan
                             - Provider registry initialization
                             - DB + Redis lifecycle (init/close)
                             - Exception handler registration
                             - Router inclusion (all phases)
```

---

## Data Model

```
organizations
  id (PK)
  name, slug
  created_at

    │  1:N
    ▼

teams
  id (PK)
  organization_id (FK → organizations.id, CASCADE)
  name, slug
  created_at

    │  1:N                           │  1:1 (unique)
    ▼                                ▼

api_keys                          budgets
  id (PK)                           id (PK)
  team_id (FK → teams.id)           team_id (FK → teams.id, CASCADE)
  name                              limit_amount FLOAT
  key_hash (never exposed)          current_usage FLOAT
  role (admin | member)             reserved FLOAT   ← in-flight reservation
  created_at                        period (daily | weekly | monthly)
  expires_at (nullable)             period_start, period_end
  revoked_at (nullable)             policy (BLOCK | WARN | DOWNGRADE)
                                    enabled BOOL
                                    created_at, updated_at
```

---

## Phase 6 Redis Key Schema

```
Rate Limiting (fixed-window counters):

  ratelimit:key:<api_key_id>:<window_start>   TTL = window_seconds
  ratelimit:team:<team_id>:<window_start>      TTL = window_seconds
  ratelimit:org:<org_id>:<window_start>        TTL = window_seconds

  window_start = floor(time.time() / window_seconds) * window_seconds
  → All windows are epoch-aligned; counters auto-expire via Redis TTL.
  → Lua script: INCR + EXPIRE (on count==1) in a single atomic operation.
  → No separate scheduler or cleanup needed.
```

---

## Phase 6 Budget Concurrency Model

```
Concurrent request scenario (both try to spend $4 from $5 remaining):

  Request A                     Request B
       │                              │
       │  SELECT FOR UPDATE           │  SELECT FOR UPDATE (BLOCKED)
       │  ← acquires row lock →       │
       │                              │
       │  current_usage = 1.00        │
       │  reserved     = 0.00         │
       │  remaining    = 4.00         │
       │                              │
       │  estimated_cost = 4.00       │
       │  4.00 ≤ 4.00 → OK           │
       │  reserved = 4.00             │
       │  COMMIT + release lock       │
       │                              │  ← lock released
       │                              │  SELECT FOR UPDATE (acquired)
       │                              │  remaining = limit - usage - reserved
       │                              │           = 5 - 1 - 4 = 0.00
       │                              │  0.00 + 4.00 > 0.00 → REJECT
       │                              │  → 402 BUDGET_EXCEEDED
       ▼                              ▼
  Provider call                  Client error
       │
  actual = 3.50
  reserved -= 4.00  (→ 0)
  usage    += 3.50  (→ 4.50)
  COMMIT
```

---

## Phase 6 Cost Pricing Model

```
ModelMetadata (app/routing/models.py):
  cost_per_1k_tokens   → used by Phase 3 routing scorer (blended)
  input_cost_per_1k    → used by Phase 6 CostCalculator (accurate billing)
  output_cost_per_1k   → used by Phase 6 CostCalculator (accurate billing)

Pricing catalog (app/routing/metadata.py) — source prices:
  gemini-1.5-flash:   $0.000075 / 1K input   $0.000300 / 1K output
  gemini-1.5-pro:     $0.001250 / 1K input   $0.005000 / 1K output
  gemini-2.0-flash:   $0.000100 / 1K input   $0.000400 / 1K output
  llama-3.3-70b:      $0.000590 / 1K input   $0.000790 / 1K output (Groq)
  llama-3.1-8b:       $0.000050 / 1K input   $0.000080 / 1K output (Groq)
  ollama/*:           $0.000000 / 1K input   $0.000000 / 1K output (configurable)

Estimation formula:
  input_tokens  = len(messages_content) / 4  (1 token ≈ 4 chars)
  output_tokens = request.max_tokens or 500   (default estimate)
  estimate      = (input/1000 × input_price + output/1000 × output_price) × 1.5

Actual formula (post-execution):
  actual = (prompt_tokens/1000 × input_price)
         + (completion_tokens/1000 × output_price)
  Fallback: if usage is None → use estimate (never silently zero)
```

---

## Security Design

### Authentication (Phase 5)
- **Key format:** `cxg_<32-byte-urlsafe-base64>` (CSPRNG, 256-bit entropy)
- **Storage:** HMAC-SHA256(pepper + key), never plaintext
- **Verification:** `hmac.compare_digest` (constant-time, timing-attack resistant)
- **Pepper:** Server-side secret injected from env, rotatable
- **Lifecycle:** Keys shown plaintext exactly once at creation
- **Revocation:** Soft-delete (`revoked_at`) — preserved for audit, rejected on auth

### Authorization (Phase 5)
- **Roles:** `admin` (full access) and `member` (chat only)
- **Enforcement:** `require_admin` FastAPI dependency — server-side, not client-controlled
- **Cross-tenant isolation:** All team/org lookups validate `organization_id` matches authenticated context
- **No client trust:** `team_id`, `org_id`, `role` always come from `RequestContext`, never from request body

### Rate Limiting (Phase 6)
- **Ownership:** Limiter always uses `context.api_key_id`, `context.team_id`, `context.organization_id`
- **No client override:** Rate limit identifiers are never taken from the request body
- **Fail-open:** Redis unavailability → allow traffic (prevent total outage), log warning
- **Hierarchy:** Key ∩ Team ∩ Org — all three must pass

### Budget (Phase 6)
- **No client override:** `team_id` always taken from authenticated `RequestContext`
- **Admin-only management:** Budget CRUD requires `role=admin`
- **Cross-org blocked:** `_resolve_team()` validates `team_id` belongs to authenticated `organization_id`
- **Reserved field never exposed:** Only `remaining_amount` (derived) returned in API responses
- **Provider failure = no charge:** `release_reservation()` called on exception, no phantom billing

---

## Alembic Migration History

| Revision | Description | Tables |
|----------|-------------|--------|
| `0001` | Phase 5 Auth | `organizations`, `teams`, `api_keys` |
| `0002` | Phase 6 Budgets | `budgets` |

Run migrations:
```bash
cd backend
alembic upgrade head
```

---

## Test Architecture

```
tests/
├── conftest.py                  Session-scoped TestClient; patches init_db/init_redis
├── test_endpoints.py            Phase 1: health, root, version
├── test_providers.py            Phase 2: provider unit tests (mocked HTTP)
├── test_chat_api.py             Phase 2–6: chat endpoint integration tests
│                                Phase 6 deps overridden with no-ops in fixture
├── test_routing.py              Phase 3: candidate scoring, mode resolution
├── test_reliability.py          Phase 4: circuit breaker, retry, failover
├── test_auth_security.py        Phase 5: key generation, HMAC, constant-time compare
├── test_auth_lifecycle.py       Phase 5: create/list/revoke + RBAC
├── test_auth_security_leakage.py Phase 5: key_hash never in response
├── test_rate_limiting.py        Phase 6: Lua mock, all 3 scopes, ownership
└── test_budget.py               Phase 6: cost calc, BLOCK/WARN rollover, reconcile

Total: 238 tests — 0 failures — no real API credentials needed
```
