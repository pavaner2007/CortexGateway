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

### Currently Available
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
- ✅ **33 automated tests** — run without Docker, all dependencies mocked

### Coming Soon
- 🤖 Unified Multi-LLM API (OpenAI · Gemini · Groq · Anthropic)
- 🔐 Authentication & API key management
- 👥 Teams & organizations
- 🚦 Rate limiting & budget controls
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
33 passed in 0.30s ✅
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

Full API docs → http://localhost:8000/docs

---

## Project Structure

```
CortexGateway/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/
│   │   │   └── health.py          # GET /, /version, /health
│   │   ├── config/
│   │   │   └── settings.py        # Pydantic Settings v2
│   │   ├── core/
│   │   │   └── logging.py         # Loguru configuration
│   │   ├── database/
│   │   │   └── session.py         # SQLAlchemy 2.x async engine
│   │   ├── middleware/
│   │   │   ├── request_id.py      # X-Request-ID propagation
│   │   │   └── logging.py         # Request/response logging
│   │   ├── schemas/
│   │   │   └── responses.py       # Shared Pydantic v2 models
│   │   ├── utils/
│   │   │   └── redis_client.py    # Async Redis client
│   │   ├── exceptions.py          # Global exception handlers
│   │   └── main.py                # FastAPI app + lifespan
│   ├── tests/
│   │   ├── conftest.py            # Fixtures (DB/Redis mocked)
│   │   └── test_endpoints.py      # 33 endpoint tests
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
| 2 | Unified Multi-LLM Gateway | 🔜 Next |
| 3 | Authentication & API Keys | ⏳ Planned |
| 4 | Teams & Organizations | ⏳ Planned |
| 5 | Rate Limiting & Budgets | ⏳ Planned |
| 6 | Provider Failover & Circuit Breakers | ⏳ Planned |
| 7 | Cost Tracking & Analytics | ⏳ Planned |
| 8 | Prometheus & OpenTelemetry | ⏳ Planned |
| 9 | Admin Dashboard | ⏳ Planned |
| 10 | Production Hardening | ⏳ Planned |

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
