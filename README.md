# Cortex Gateway

**Intelligent Multi-LLM Gateway and AI Infrastructure Platform**

> Phase 1 of 10 — Foundation and Project Setup

---

## Project Overview

Cortex Gateway is a centralized AI infrastructure platform that will sit between
client applications and multiple LLM providers. It provides a single, unified
interface for routing, observability, rate limiting, cost tracking, and failover
across providers like OpenAI, Gemini, Groq, and Anthropic.

**Phase 1** establishes the production-quality project skeleton: FastAPI backend,
React frontend, PostgreSQL, Redis, Docker Compose, structured logging, request ID
propagation, global error handling, and health monitoring.

---

## Phase 1 Scope

What is implemented in this phase:

- ✅ FastAPI backend (Python 3.12, async I/O)
- ✅ React + TypeScript + Vite + Tailwind CSS frontend
- ✅ PostgreSQL (SQLAlchemy 2.x + asyncpg)
- ✅ Redis (async client)
- ✅ Docker Compose (4-service stack)
- ✅ Environment configuration (pydantic-settings)
- ✅ Structured logging (Loguru)
- ✅ Request ID propagation (X-Request-ID)
- ✅ Global error handling (consistent JSON envelope)
- ✅ Health checks with independent dependency reporting
- ✅ Swagger UI and ReDoc API documentation
- ✅ Automated endpoint tests (no Docker required)

What is **NOT** implemented (deferred to later phases):

- ❌ LLM provider adapters
- ❌ Unified chat API
- ❌ Authentication / API keys
- ❌ Rate limiting / budgets
- ❌ Analytics / Prometheus / OpenTelemetry
- ❌ Teams / organizations

---

## Architecture

```
React Frontend  (port 5173)
       │
       ▼
FastAPI Backend  (port 8000)
       │
  ┌────┴────┐
  ▼         ▼
PostgreSQL  Redis
(port 5432) (port 6379)
```

**Request flow:**

```
Client → RequestIDMiddleware → RequestLoggingMiddleware → Route Handler
                                                              │
                                                    DB/Redis Health Checks
                                                              │
                                                       JSON Response
```

---

## Prerequisites

| Tool | Minimum Version |
|------|----------------|
| Docker | 24+ |
| Docker Compose | v2.20+ |
| Python | 3.12+ (local dev only) |
| Node.js | 22+ (local dev only) |

---

## Environment Setup

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and change:

| Variable | Description |
|----------|-------------|
| `POSTGRES_PASSWORD` | PostgreSQL password (change from default) |
| `SECRET_KEY` | Application secret key (min 32 chars in production) |

All other variables have safe development defaults.

**URL auto-composition**: `DATABASE_URL` and `REDIS_URL` are automatically
built from component variables (`POSTGRES_HOST`, `POSTGRES_PORT`, etc.).
Leave them blank unless you need to override (e.g., managed database service).

---

## Docker Setup

```bash
# Build and start all services
docker compose up --build

# Start in background
docker compose up --build -d

# Stop all services
docker compose down

# Stop and remove volumes
docker compose down -v
```

### Service URLs

| Service | URL |
|---------|-----|
| Frontend Dashboard | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Health Endpoint | http://localhost:8000/health |

---

## Local Development

### Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate (Linux/macOS)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Start with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> **Note**: The backend will start even without PostgreSQL or Redis running.
> Health checks will report `disconnected` until those services are available.

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Open http://localhost:5173

### Tests

```bash
cd backend

# Run all tests (no Docker required)
pytest tests/ -v

# Run with coverage
pytest tests/ -v --tb=short
```

---

## Health Check

```bash
# All healthy
curl http://localhost:8000/health

# Expected (healthy):
# {"status":"healthy","database":"connected","redis":"connected","version":"1.0.0"}

# Expected (degraded, HTTP 503):
# {"status":"degraded","database":"disconnected","redis":"connected","version":"1.0.0"}
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Application info |
| GET | `/version` | Application version |
| GET | `/health` | System health check |
| GET | `/docs` | Swagger UI |
| GET | `/redoc` | ReDoc documentation |

---

## Project Structure

```
cortex-gateway/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/
│   │   │   └── health.py        # GET /, /version, /health
│   │   ├── config/
│   │   │   └── settings.py      # Pydantic Settings (env vars)
│   │   ├── core/
│   │   │   └── logging.py       # Loguru configuration
│   │   ├── database/
│   │   │   └── session.py       # SQLAlchemy 2.x async engine
│   │   ├── middleware/
│   │   │   ├── request_id.py    # X-Request-ID propagation
│   │   │   └── logging.py       # Request/response logging
│   │   ├── schemas/
│   │   │   └── responses.py     # Shared Pydantic v2 schemas
│   │   ├── utils/
│   │   │   └── redis_client.py  # Async Redis client
│   │   ├── exceptions.py        # Global error handlers
│   │   └── main.py              # FastAPI app + lifespan
│   ├── tests/
│   │   ├── conftest.py          # Fixtures (mocked DB/Redis)
│   │   └── test_endpoints.py    # Endpoint tests
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── pytest.ini
│   ├── .env.example
│   └── .env                     # gitignored
│
├── frontend/
│   ├── src/
│   │   ├── api/health.ts        # Backend API integration
│   │   ├── components/
│   │   │   ├── Layout.tsx       # Sidebar + header shell
│   │   │   └── StatusCard.tsx   # Reusable status card
│   │   ├── pages/
│   │   │   └── Dashboard.tsx    # System status dashboard
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
│
├── docs/
│   └── architecture.md          # Detailed architecture docs
│
├── docker-compose.yml
├── .gitignore
├── LICENSE
└── README.md
```

---

## Phase Roadmap

| Phase | Title | Status |
|-------|-------|--------|
| **1** | **Foundation and Project Setup** | ✅ **Complete** |
| 2 | Unified Multi-LLM Gateway | ⏳ Pending |
| 3 | Authentication and API Keys | ⏳ Pending |
| 4 | Teams and Organizations | ⏳ Pending |
| 5 | Rate Limiting and Budgets | ⏳ Pending |
| 6 | Provider Health Monitoring and Failover | ⏳ Pending |
| 7 | Request Analytics and Cost Tracking | ⏳ Pending |
| 8 | Observability (Prometheus, OpenTelemetry) | ⏳ Pending |
| 9 | Admin Dashboard | ⏳ Pending |
| 10 | Production Hardening and Deployment | ⏳ Pending |

---

## License

MIT — see [LICENSE](LICENSE)
