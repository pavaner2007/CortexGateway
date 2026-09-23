# Cortex Gateway — Load Testing with Locust

## Overview

Load tests exercise the Cortex Gateway API using [Locust](https://locust.io/).

**Target endpoint:** `POST /api/v1/chat/completions`

**Intended target:** Ollama (local provider) — no external API cost or quota consumption.

> ⚠️ **Do NOT run against live Gemini/Groq endpoints** without controlling for API costs and rate limits. Use Ollama or a staging environment.

## Prerequisites

```bash
pip install locust
```

A running Cortex Gateway with at least one provider configured (Ollama recommended):
```bash
docker compose up -d
docker compose exec backend alembic upgrade head
# Bootstrap and create an API key
```

## Quick Start

```bash
cd load_tests/

# Set your API key
export CORTEX_API_KEY=your-api-key-here
export CHAT_MODEL=ollama/llama3.2:1b   # smallest/fastest Ollama model

# Web UI (opens http://localhost:8089)
locust -f locustfile.py --host http://localhost:8000

# Headless — 10 users, 2/s spawn, 2 minutes
locust -f locustfile.py \
  --host http://localhost:8000 \
  --users 10 \
  --spawn-rate 2 \
  --run-time 2m \
  --headless \
  --only-summary
```

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `CORTEX_API_KEY` | (empty) | API key for authenticated requests |
| `CHAT_MODEL` | `ollama/llama3.2:1b` | Model to use in chat requests |
| `CHAT_PROMPT` | Short benign prompt | Prompt text for chat requests |

## Scenarios

| User Class | Weight | Description |
|---|---|---|
| `HealthUser` | 10% | GET /health, GET /version — lightweight baseline |
| `ChatUser` | 80% | POST /api/v1/chat/completions — primary load scenario |
| `RateLimitUser` | 10% | Rapid requests to observe rate-limiting behavior |

`ChatUser` tasks:
- **standard (5x weight):** Normal chat request
- **cache-test (2x weight):** Repeated identical prompt — exercises semantic cache if enabled
- **auto-routing (1x weight):** `model=auto` to test intelligent routing

## Baseline Parameters

Conservative baseline for a single-machine deployment with Ollama:

```
Users:       10
Spawn rate:  2/s
Duration:    5 minutes
Model:       ollama/llama3.2:1b
```

Adjust based on your environment. Ollama response latency varies significantly by:
- GPU vs CPU inference
- Model size (1B params << 70B params)
- Available RAM/VRAM

## Expected Behaviors to Observe

| Behavior | What to watch |
|---|---|
| **Rate limiting** | 429 responses from `RateLimitUser` after limit hit |
| **Circuit breaker** | 503/fallback if provider fails repeatedly |
| **Cache hits** | Lower latency on repeated identical prompts (if `SEMANTIC_CACHE_ENABLED=true`) |
| **Budget exhaustion** | 402 responses if team budget is configured and exhausted |
| **Graceful degradation** | Gateway stays responsive even when one provider is down |

## Load Test Results

> **Status: NOT VERIFIED**
>
> Actual load test results were not collected during Phase 10 because a running
> Cortex Gateway + Ollama stack was not available in the CI/test environment.
>
> To collect results:
> 1. Start the full stack: `docker compose up -d`
> 2. Pull an Ollama model: `docker compose exec ollama ollama pull llama3.2:1b`
> 3. Bootstrap and create an API key
> 4. Run: `locust -f load_tests/locustfile.py --host http://localhost:8000 --users 10 --spawn-rate 2 -t 5m --headless --only-summary`
> 5. Report the actual p95/p99 latency, RPS, and error rate

## Interpreting Results

| Metric | Healthy Baseline (Ollama CPU) |
|---|---|
| Avg latency | 2–15s (LLM generation time) |
| p95 latency | < 30s |
| Error rate | < 1% |
| Rate-limited (429) | Expected from `RateLimitUser` |
| Failed (5xx) | Should be 0 under normal load |
