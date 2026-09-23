# Cortex Gateway — Deployment Guide

> **Version:** 1.0.0 | **Phases covered:** 1 – 9E + Phase 10 Production

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (Development)](#quick-start-development)
3. [Production Docker Compose](#production-docker-compose)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Environment Variables](#environment-variables)
6. [Database Migrations](#database-migrations)
7. [Ollama Architecture](#ollama-architecture)
8. [Backup and Restore](#backup-and-restore)
9. [Troubleshooting](#troubleshooting)
10. [Known Limitations](#known-limitations)
11. [API Reference (Quick Start)](#api-reference-quick-start)

---

## Prerequisites

### Docker Compose (development / production demo)

| Dependency | Minimum | Notes |
|---|---|---|
| Docker | 24.x | |
| Docker Compose | v2.20+ | (`docker compose`, not `docker-compose`) |
| Git | any | |

### Kubernetes

| Dependency | Notes |
|---|---|
| kubectl | Configured against target cluster |
| Kubernetes | 1.27+ recommended |
| Managed PostgreSQL | RDS, Cloud SQL, Supabase, etc. |
| Managed Redis | ElastiCache, Redis Cloud, etc. |
| Ingress controller | nginx-ingress recommended |

### Local development only

| Dependency | Notes |
|---|---|
| Python | 3.12 |
| Node.js | 22 |
| PostgreSQL | 16 (or via Docker) |
| Redis | 7 (or via Docker) |

---

## Quick Start (Development)

```bash
# 1. Clone
git clone https://github.com/yourorg/cortex-gateway.git
cd cortex-gateway

# 2. Configure backend environment
cp backend/.env.example backend/.env
# Edit backend/.env — at minimum change:
#   POSTGRES_PASSWORD, SECRET_KEY, API_KEY_PEPPER, CORTEX_BOOTSTRAP_TOKEN
#   Add GEMINI_API_KEY and/or GROQ_API_KEY if using cloud providers

# 3. Start all services
docker compose up --build -d

# 4. Run database migrations
docker compose exec backend alembic upgrade head

# 5. Verify health
curl http://localhost:8000/health

# 6. Bootstrap — create the first organization and admin API key
curl -X POST http://localhost:8000/api/v1/bootstrap \
  -H "Content-Type: application/json" \
  -H "X-Bootstrap-Token: <CORTEX_BOOTSTRAP_TOKEN from .env>" \
  -d '{"organization_name": "My Org", "team_name": "Engineering"}'
# Save the returned api_key — it is shown ONCE

# 7. Test a chat request
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -d '{"model": "auto", "messages": [{"role": "user", "content": "Hello!"}]}'

# 8. Access the admin dashboard
open http://localhost:5173
```

### Service ports (development)

| Port | Service |
|---|---|
| 8000 | Backend API (also `/docs`, `/redoc`, `/metrics`) |
| 5173 | Frontend admin dashboard |
| 5432 | PostgreSQL (local tooling access) |
| 6379 | Redis (local tooling access) |
| 11434 | Ollama |
| 9090 | Prometheus |
| 3000 | Grafana (admin/admin) |

---

## Production Docker Compose

### 1. Build images

```bash
# Backend
docker build -t cortex-backend:latest ./backend

# Frontend (empty VITE_API_URL = relative URLs through NGINX proxy)
docker build -t cortex-frontend:latest ./frontend --build-arg VITE_API_URL=
```

### 2. Configure environment

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` for production — **critical changes**:

```env
ENVIRONMENT=production
POSTGRES_PASSWORD=<strong-random-password>
SECRET_KEY=<32+-char-random-string>
API_KEY_PEPPER=<32+-char-random-string>
CORTEX_BOOTSTRAP_TOKEN=<strong-random-token>
CORTEX_BOOTSTRAP_ENABLED=true   # set false after first bootstrap
GEMINI_API_KEY=<your-key>        # or leave blank to disable
GROQ_API_KEY=<your-key>          # or leave blank to disable
CORS_ORIGINS=https://your-domain.com
```

Generate secrets:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Start production stack

```bash
docker compose -f docker-compose.prod.yml up -d
```

### 4. Run migrations (every deploy)

```bash
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### 5. Verify

```bash
# Health
curl http://localhost/health

# Version
curl http://localhost/version

# Frontend
curl http://localhost/
```

### Production ports

| Port | Service |
|---|---|
| 80 | NGINX (frontend + API) |
| 3000 | Grafana (optional) |
| 9090 | Prometheus (optional, internal) |

> **Note:** PostgreSQL (5432) and Redis (6379) are **not exposed** to the host in production Compose — accessible only within the Docker internal network.

---

## Kubernetes Deployment

> **Status:** Manifests are verified for YAML syntax. Cluster deployment is **not verified** — no Kubernetes cluster was available during Phase 10.

### Recommended production architecture

- **PostgreSQL:** Managed external service (RDS, Cloud SQL, Supabase)
- **Redis:** Managed external service (ElastiCache, Redis Cloud)
- **Ollama:** Separate GPU host or GPU-enabled node (see [Ollama Architecture](#ollama-architecture))

### Deploy

```bash
# 1. Create namespace
kubectl apply -f k8s/namespace.yaml

# 2. Populate secrets (using kubectl — see k8s/secret.yaml for all keys)
kubectl create secret generic cortex-gateway-secrets \
  --namespace cortex-gateway \
  --from-literal=POSTGRES_PASSWORD=<password> \
  --from-literal=SECRET_KEY=<secret> \
  --from-literal=API_KEY_PEPPER=<pepper> \
  --from-literal=CORTEX_BOOTSTRAP_TOKEN=<token> \
  --from-literal=GEMINI_API_KEY=<key> \
  --from-literal=GROQ_API_KEY=<key> \
  --from-literal=OPENAI_API_KEY="" \
  --from-literal=GF_ADMIN_PASSWORD=<grafana-password>

# 3. Update ConfigMap values for your environment
#    Edit k8s/configmap.yaml — update POSTGRES_HOST, REDIS_HOST, CORS_ORIGINS, etc.
kubectl apply -f k8s/configmap.yaml

# 4. Deploy backend
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/backend-service.yaml

# 5. Deploy frontend
kubectl apply -f k8s/frontend-deployment.yaml

# 6. Configure Ingress (update host in k8s/ingress.yaml first)
kubectl apply -f k8s/ingress.yaml

# 7. Run migrations
kubectl exec -n cortex-gateway \
  $(kubectl get pod -n cortex-gateway -l app=cortex-backend -o jsonpath='{.items[0].metadata.name}') \
  -- alembic upgrade head

# 8. Verify
kubectl get pods -n cortex-gateway
kubectl get ingress -n cortex-gateway
```

### Ollama in Kubernetes (optional)

```bash
# Only if running Ollama inside the cluster (see k8s/ollama-deployment.yaml)
kubectl apply -f k8s/ollama-deployment.yaml

# Pre-pull models before serving traffic
kubectl exec -n cortex-gateway \
  $(kubectl get pod -n cortex-gateway -l app=ollama -o jsonpath='{.items[0].metadata.name}') \
  -- ollama pull llama3.2:1b
```

### Health probe design

| Probe | Endpoint | Rationale |
|---|---|---|
| `livenessProbe` | `GET /version` | Process-only check — no DB/Redis; prevents unnecessary restarts during transient outages |
| `readinessProbe` | `GET /health` | Checks DB + Redis; pod only receives traffic when fully ready |
| `startupProbe` | `GET /health` | 60s window for initial startup before liveness kicks in |

---

## Environment Variables

See [`backend/.env.example`](../backend/.env.example) for the complete list with descriptions.

### Required to change before production

| Variable | Why |
|---|---|
| `POSTGRES_PASSWORD` | Default is insecure placeholder |
| `SECRET_KEY` | Must be unique per deployment |
| `API_KEY_PEPPER` | Changing this invalidates all existing API keys |
| `CORTEX_BOOTSTRAP_TOKEN` | Protects first-admin creation |

### Total count: 69 environment variables

| Group | Count |
|---|---|
| Application | 4 |
| API Server | 2 |
| Database | 6 |
| Redis | 3 |
| Security | 1 |
| Logging | 1 |
| CORS | 1 |
| Providers (global) | 3 |
| Gemini | 3 |
| Groq | 4 |
| OpenAI | 3 |
| Ollama | 3 |
| Routing (Phase 3) | 7 |
| Reliability (Phase 4) | 9 |
| Auth/Bootstrap (Phase 5) | 4 |
| Rate Limiting (Phase 6) | 7 |
| Budget (Phase 6) | 6 |
| Observability (Phase 7) | 5 |
| Semantic Cache (Phase 9B) | 7 |
| Frontend | 1 |
| **Phase 9C/9D/9E** | 0 (policy-managed via API, not env vars) |

---

## Database Migrations

All schema changes are managed via Alembic. Never manually alter tables.

### Migration history

| Migration | Phase | Description |
|---|---|---|
| `0001_phase5_auth` | 5 | Organizations, teams, API keys, RBAC |
| `0002_phase6_budgets` | 6 | Team budgets |
| `0003_phase6_team_rate_limits` | 6 | Per-team rate limit config |
| `0004_phase7_request_logs` | 7 | Request analytics log |
| `0005_phase9a_model_registry` | 9A | Model registry catalog |
| `0006_phase9b_semantic_cache` | 9B | Semantic cache entries |
| `0007_phase9c_team_policies` | 9C | Team policy JSONB column |
| `0008_phase9d_experiment_log` | 9D | Experiment assignment log |
| `0009_phase9e_guardrail_log` | 9E | Guardrail triggered/action columns |

### Production migration procedure

```bash
# 1. BACKUP the database first (see Backup section)

# 2. Deploy the new application image

# 3. Run migration (from inside the backend container)
docker compose exec backend alembic upgrade head

# 4. Verify current migration version
docker compose exec backend alembic current

# 5. Verify application starts and /health returns 200

# Rollback (one step):
docker compose exec backend alembic downgrade -1
```

> **Warning:** Downgrading removes schema changes. Always backup before migrating.

---

## Ollama Architecture

Ollama is a local, self-hosted LLM runtime. It is **not** a cloud API.

### Connectivity requirement

The Cortex Gateway backend must be able to reach Ollama at `OLLAMA_BASE_URL`.

### Supported architectures

**Option A: Same-host Docker Compose (development/demo)**
```
docker-compose.yml
  backend → ollama (internal Docker network at http://ollama:11434)
```

**Option B: External GPU host (recommended production)**
```
Cortex Gateway (any host)
  ↓ OLLAMA_BASE_URL=http://<gpu-host-ip>:11434
GPU host running: ollama serve
```

**Option C: Kubernetes with GPU node (advanced)**
```
kubectl apply -f k8s/ollama-deployment.yaml
# Requires: GPU-enabled node, tolerations, PVC for model storage
# See k8s/ollama-deployment.yaml for configuration
```

### Model management

```bash
# List available models
ollama list

# Pull a model (do this before traffic, not during deployment)
ollama pull llama3.2:1b         # ~1.3GB — fast, minimal
ollama pull llama3.1:8b         # ~4.7GB — good quality
ollama pull nomic-embed-text    # for semantic cache (Phase 9B)

# Verify Ollama is reachable from the gateway
curl http://<OLLAMA_BASE_URL>/api/tags
```

> **Important:** The gateway does **not** automatically pull models. Missing models return a 404/503 from the Ollama provider adapter.

---

## Backup and Restore

### PostgreSQL backup

```bash
# Full backup (Docker Compose)
docker compose exec postgres pg_dump \
  -U cortex_user cortex_gateway \
  > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore
docker compose exec -T postgres psql \
  -U cortex_user cortex_gateway \
  < backup_20260923_120000.sql

# Kubernetes (managed DB — use your provider's backup mechanism)
# RDS: automated snapshots + manual snapshot before migrations
# Cloud SQL: automated backups + on-demand backups
```

### Redis backup

Redis contains only:
- Rate limit counters (TTL-bounded, auto-expire)
- Semantic cache entries (TTL-bounded, auto-expire)

**Redis data is ephemeral and non-critical.** The application is fully functional after Redis restart; counters reset and cache entries are cold-start rebuilt.

For persistence, the production Compose uses `redis-server --save 60 1` (RDB snapshot every 60s if 1 key changed).

---

## Troubleshooting

### Backend cannot connect to PostgreSQL

```bash
# Check DB is healthy
docker compose ps postgres

# Check connection string
docker compose exec backend python -c \
  "from app.config.settings import get_settings; print(get_settings().database_url)"

# Tail backend logs
docker compose logs backend --tail=50
```

**Common causes:**
- `POSTGRES_PASSWORD` mismatch between `.env` and `POSTGRES_PASSWORD` env var
- `POSTGRES_HOST` not matching Docker service name (`postgres` in Compose, external hostname in prod)
- DB not yet healthy — check `docker compose ps`

### Backend cannot connect to Redis

```bash
docker compose logs redis --tail=20
docker compose exec redis redis-cli ping
```

### Ollama unreachable

```bash
# Test from backend container
docker compose exec backend curl http://ollama:11434/api/tags

# If using external host:
curl http://<OLLAMA_BASE_URL>/api/tags
```

**Common causes:**
- `OLLAMA_BASE_URL` set to `http://localhost:11434` inside Docker (should be `http://ollama:11434`)
- Ollama not started on the host
- Firewall blocking port 11434

### Ollama model not found

```bash
# List available models
docker compose exec ollama ollama list

# Pull the required model
docker compose exec ollama ollama pull llama3.2:1b
```

### Provider API key missing

The gateway logs a warning at startup but does not crash:
```
Gemini provider skipped (disabled or missing API key)
```

Check your `.env` contains `GEMINI_API_KEY=<your-key>` and `GEMINI_ENABLED=true`.

### Circuit breaker opens unexpectedly

Check backend logs for:
```
circuit_breaker_state=open provider=gemini
```

The circuit breaker opens after `CIRCUIT_BREAKER_FAILURE_THRESHOLD` (default: 5) consecutive provider failures within the window. Cooldown period: `CIRCUIT_BREAKER_COOLDOWN_SECONDS` (default: 30s).

Reset: wait for cooldown to expire. The breaker will enter half-open state and retry automatically.

### Rate limit unexpectedly triggered

Check rate limit config in `.env`:
```
RATE_LIMIT_API_KEY_REQUESTS=100
RATE_LIMIT_API_KEY_WINDOW_SECONDS=60
```

The `X-RateLimit-*` headers in the response show remaining quota.

### Budget blocks requests (402)

Check team budget configuration via the API:
```bash
curl http://localhost:8000/api/v1/budgets \
  -H "Authorization: Bearer <admin-api-key>"
```

Budget can be reset or increased via the budget management API.

### Frontend cannot reach backend

In production Compose: NGINX proxies `/api/*` to `backend:8000`.
Check:
```bash
docker compose logs nginx --tail=20
curl http://localhost/health   # via NGINX
curl http://localhost:8000/health  # direct (dev only)
```

In Kubernetes: check Ingress routing and backend Service:
```bash
kubectl describe ingress cortex-gateway-ingress -n cortex-gateway
kubectl get endpoints cortex-backend -n cortex-gateway
```

### Migration failures

```bash
# Check current migration state
docker compose exec backend alembic current

# Check full migration history
docker compose exec backend alembic history

# Verbose migration output
docker compose exec backend alembic upgrade head --sql
```

If migration fails mid-way, restore from backup and investigate before re-running.

### Container permission problems

The backend runs as non-root user `cortex` (uid 1000). If you see permission errors:
- Check that volume mounts are owned/accessible by uid 1000
- Verify the Dockerfile `chown -R cortex:cortex /app` ran successfully

### Kubernetes readiness failures

```bash
kubectl describe pod <pod-name> -n cortex-gateway
kubectl logs <pod-name> -n cortex-gateway --previous
```

Readiness probe (`GET /health`) checks both PostgreSQL and Redis. If either is unavailable, the pod is removed from the load balancer but NOT restarted (liveness uses `/version`).

---

## Known Limitations

| Limitation | Detail |
|---|---|
| **PII detection is heuristic** | Regex-based; will have false positives and negatives. Not a compliance boundary. |
| **Injection detection is heuristic** | Phrase-matching only; not a complete prompt injection defense. |
| **Ollama requires separate GPU compute** | Not automatically provisioned. Models must be pre-pulled. |
| **No automatic canary promotion** | A/B experiments do not auto-promote winning arms. |
| **No automatic rollback** | Failed deployments require manual intervention. |
| **No multi-region deployment** | Single-region architecture only. |
| **No service mesh** | No mTLS between services, no traffic shaping at the mesh level. |
| **No full penetration test** | Security headers and non-root containers are implemented; no formal pen test performed. |
| **No managed database provisioning** | k8s manifests assume an external managed DB; no StatefulSet provided. |
| **No automatic disaster recovery** | Backup/restore procedures are documented but not automated. |
| **OpenTelemetry not installed in test env** | 108 tests require `opentelemetry` installed — excluded from CI until resolved. |
| **Kubernetes cluster not verified** | Manifests are syntax-verified only; no actual cluster deployment was performed during Phase 10. |
| **Load test not executed** | Locust file is implemented; results cannot be reported without a running gateway + Ollama. |
| **mypy typing debt** | Several third-party packages lack stubs; `disallow_untyped_defs = false` in mypy config. |

---

## API Reference (Quick Start)

Replace `$BASE_URL` with your gateway URL (e.g., `http://localhost:8000`) and `$API_KEY` with your API key.

### Health

```bash
curl $BASE_URL/health
curl $BASE_URL/version
```

### Bootstrap (first-time setup)

```bash
curl -X POST $BASE_URL/api/v1/bootstrap \
  -H "Content-Type: application/json" \
  -H "X-Bootstrap-Token: $CORTEX_BOOTSTRAP_TOKEN" \
  -d '{"organization_name": "My Org", "team_name": "Engineering"}'
```

### Chat completion

```bash
curl -X POST $BASE_URL/api/v1/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Team policy (guardrails + routing)

```bash
curl -X PUT $BASE_URL/api/v1/teams/$TEAM_ID/policy \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "guardrails": {
      "max_prompt_length": 4096,
      "pii_detection": "block",
      "injection_detection": "warn"
    },
    "routing": {"mode": "lowest_cost"}
  }'
```

### Model registry

```bash
curl $BASE_URL/api/v1/models \
  -H "Authorization: Bearer $API_KEY"
```

### Analytics

```bash
curl "$BASE_URL/api/v1/analytics/requests?limit=20" \
  -H "Authorization: Bearer $API_KEY"
```

### OpenAPI documentation

```
http://localhost:8000/docs       # Swagger UI
http://localhost:8000/redoc      # ReDoc
http://localhost:8000/openapi.json  # raw schema
```
