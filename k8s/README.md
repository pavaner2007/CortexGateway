# Cortex Gateway — Kubernetes Manifests

## Overview

This directory contains baseline Kubernetes manifests for deploying Cortex Gateway.

```
k8s/
├── namespace.yaml           # cortex-gateway namespace
├── configmap.yaml           # Non-sensitive configuration
├── secret.yaml              # Secret template (never commit real values)
├── backend-deployment.yaml  # FastAPI backend (2 replicas)
├── backend-service.yaml     # Backend ClusterIP service
├── frontend-deployment.yaml # React/nginx frontend (2 replicas) + service
├── ingress.yaml             # NGINX Ingress (routes /api/* → backend, / → frontend)
├── ollama-deployment.yaml   # OPTIONAL: Ollama in-cluster (GPU required)
└── README.md                # This file
```

## Production Architecture Assumptions

| Component | Recommendation |
|---|---|
| **PostgreSQL** | External managed service (RDS, Cloud SQL, Supabase) |
| **Redis** | External managed service (ElastiCache, Redis Cloud) |
| **Ollama** | Separate GPU host OR GPU-enabled K8s node (see below) |
| **TLS** | cert-manager + Let's Encrypt (see Ingress comments) |

## Deployment Steps

```bash
# 1. Namespace
kubectl apply -f k8s/namespace.yaml

# 2. Secrets — populate with real values (see secret.yaml comments)
kubectl create secret generic cortex-gateway-secrets \
  --namespace cortex-gateway \
  --from-literal=POSTGRES_PASSWORD=<password> \
  --from-literal=SECRET_KEY=<secret-32+-chars> \
  --from-literal=API_KEY_PEPPER=<pepper-32+-chars> \
  --from-literal=CORTEX_BOOTSTRAP_TOKEN=<token> \
  --from-literal=GEMINI_API_KEY=<key-or-empty> \
  --from-literal=GROQ_API_KEY=<key-or-empty> \
  --from-literal=OPENAI_API_KEY="" \
  --from-literal=GF_ADMIN_PASSWORD=<grafana-password>

# 3. ConfigMap — edit POSTGRES_HOST, REDIS_HOST, CORS_ORIGINS first
kubectl apply -f k8s/configmap.yaml

# 4. Backend
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/backend-service.yaml

# 5. Frontend
kubectl apply -f k8s/frontend-deployment.yaml

# 6. Ingress — edit host in ingress.yaml first
kubectl apply -f k8s/ingress.yaml

# 7. Run migrations (once per deploy)
kubectl exec -n cortex-gateway \
  $(kubectl get pod -n cortex-gateway -l app=cortex-backend -o jsonpath='{.items[0].metadata.name}') \
  -- alembic upgrade head

# 8. Verify
kubectl get pods -n cortex-gateway
kubectl get ingress -n cortex-gateway
```

## Health Probe Design

| Probe | Endpoint | Rationale |
|---|---|---|
| `livenessProbe` | `GET /version` | Process-only — avoids unnecessary restarts on transient DB/Redis outage |
| `readinessProbe` | `GET /health` | Full check (DB + Redis) — pod removed from LB until ready |
| `startupProbe` | `GET /health` | 60s startup window before liveness engages |

> **Important:** Do NOT use `/health` as the liveness probe. `/health` checks PostgreSQL and Redis. If the DB is temporarily unreachable, liveness failure would cause Kubernetes to restart a healthy application pod — which would not help and could cascade into a restart loop. The `/version` endpoint is lightweight and reflects only process health.

## Ollama in Kubernetes

**Default recommendation: run Ollama on a separate GPU host, not inside Kubernetes.**

Reasons:
- GPU resources are not available in all clusters
- Large model weights (4–70GB) cause slow pod startup
- Models should be pre-pulled, not downloaded during deployment
- A crashed pod would lose in-flight model serving

If you must run Ollama in Kubernetes:
```bash
# Apply the optional manifest
kubectl apply -f k8s/ollama-deployment.yaml

# Pre-pull models before routing traffic
kubectl exec -n cortex-gateway \
  $(kubectl get pod -n cortex-gateway -l app=ollama -o jsonpath='{.items[0].metadata.name}') \
  -- ollama pull llama3.2:1b
```

Update `configmap.yaml`:
```yaml
OLLAMA_BASE_URL: "http://ollama-service.cortex-gateway.svc.cluster.local:11434"
```

## Verification Status

| Item | Status |
|---|---|
| YAML syntax | ✅ Verified |
| manifest structure | ✅ Verified |
| ConfigMap/Secret separation | ✅ Verified |
| securityContext (non-root) | ✅ Verified |
| resource requests/limits | ✅ Verified |
| RollingUpdate strategy | ✅ Verified |
| Split liveness/readiness probes | ✅ Verified |
| Cluster deployment | ❌ Not verified (no cluster available) |
