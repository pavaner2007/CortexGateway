"""
Cortex Gateway — Locust Load Test
==================================

Tests the POST /api/v1/chat/completions endpoint under load.

Target: Ollama local provider (no external API cost/quota).
        Requires a running Cortex Gateway with Ollama configured.

Scenarios:
  1. HealthUser      — GET /health (baseline, no auth)
  2. ChatUser        — POST /api/v1/chat/completions (primary load scenario)
  3. RateLimitUser   — rapid small requests to observe rate-limiting behavior

Configuration (via environment variables):
  TARGET_HOST     — gateway base URL (default: http://localhost:8000)
  CORTEX_API_KEY  — API key with sufficient rate limit budget
  CHAT_MODEL      — model string (default: ollama/llama3.2:1b — smallest available)
  CHAT_PROMPT     — prompt text (default: short benign prompt)

Usage:
  pip install locust
  export CORTEX_API_KEY=your-api-key
  locust -f locustfile.py --host http://localhost:8000 --users 10 --spawn-rate 2 -t 2m

  # Headless (no UI):
  locust -f locustfile.py --host http://localhost:8000 \
         --users 10 --spawn-rate 2 -t 2m \
         --headless --only-summary

  # With web UI (default: http://localhost:8089):
  locust -f locustfile.py

IMPORTANT:
  - Do NOT run against real Gemini/Groq APIs without controlling for costs.
  - Use Ollama (local) or a staging environment for load testing.
  - Load test parameters below are conservative baselines — tune to environment.
"""

import os

from locust import HttpUser, between, events, task

# ── Configuration ─────────────────────────────────────────────────────────────
API_KEY    = os.getenv("CORTEX_API_KEY", "")
CHAT_MODEL = os.getenv("CHAT_MODEL", "ollama/llama3.2:1b")
CHAT_PROMPT = os.getenv(
    "CHAT_PROMPT",
    "Reply with exactly one sentence: What is 2+2?",
)

CHAT_ENDPOINT = "/api/v1/chat/completions"
HEALTH_ENDPOINT = "/health"
VERSION_ENDPOINT = "/version"


def _auth_headers() -> dict:
    """Return Authorization header if API key is configured."""
    if API_KEY:
        return {"Authorization": f"Bearer {API_KEY}"}
    return {}


def _chat_payload(prompt: str = CHAT_PROMPT, model: str = CHAT_MODEL) -> dict:
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 50,   # keep responses short to reduce latency
    }


# ── User: Health checks (no auth, lightweight baseline) ───────────────────────
class HealthUser(HttpUser):
    """
    Exercises /health and /version endpoints only.
    Baseline: verifies the process is alive without touching DB-heavy paths.
    Weight: 10% of total traffic.
    """
    weight = 1
    wait_time = between(1, 3)

    @task(3)
    def health(self):
        with self.client.get(HEALTH_ENDPOINT, catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 503:
                # Degraded but alive — log as success for liveness purposes
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(1)
    def version(self):
        with self.client.get(VERSION_ENDPOINT, catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")


# ── User: Chat completions (primary load scenario) ────────────────────────────
class ChatUser(HttpUser):
    """
    Exercises POST /api/v1/chat/completions.
    This is the primary load scenario representing real API consumers.
    Weight: 80% of total traffic.
    """
    weight = 8
    wait_time = between(1, 5)

    @task(5)
    def chat_standard(self):
        """Standard chat completion request."""
        with self.client.post(
            CHAT_ENDPOINT,
            json=_chat_payload(),
            headers=_auth_headers(),
            catch_response=True,
            name=f"POST {CHAT_ENDPOINT} [standard]",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 429:
                # Rate limited — expected behavior, not a failure
                resp.success()
                resp.request_meta["name"] = f"POST {CHAT_ENDPOINT} [rate-limited]"
            elif resp.status_code == 402:
                # Budget exhausted — expected behavior
                resp.success()
                resp.request_meta["name"] = f"POST {CHAT_ENDPOINT} [budget-exhausted]"
            elif resp.status_code in (400, 422):
                # Client error — log as failure
                resp.failure(f"Client error {resp.status_code}: {resp.text[:200]}")
            elif resp.status_code in (502, 503, 504):
                # Provider/gateway error — failure
                resp.failure(f"Gateway error {resp.status_code}")
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(2)
    def chat_short_prompt(self):
        """Short prompt — likely to be a cache hit after first request."""
        with self.client.post(
            CHAT_ENDPOINT,
            json=_chat_payload(
                prompt="What is the capital of France?",
            ),
            headers=_auth_headers(),
            catch_response=True,
            name=f"POST {CHAT_ENDPOINT} [cache-test]",
        ) as resp:
            if resp.status_code in (200, 429, 402):
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(1)
    def chat_auto_routing(self):
        """Use model=auto to test intelligent routing."""
        payload = _chat_payload(model="auto")
        with self.client.post(
            CHAT_ENDPOINT,
            json=payload,
            headers=_auth_headers(),
            catch_response=True,
            name=f"POST {CHAT_ENDPOINT} [auto-routing]",
        ) as resp:
            if resp.status_code in (200, 429, 402, 404):
                # 404 = no provider available — expected if no providers configured
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")


# ── User: Rate-limit boundary ─────────────────────────────────────────────────
class RateLimitUser(HttpUser):
    """
    Rapid requests to observe rate-limiting behavior.
    Expected: 429 responses after limit is hit.
    Weight: 10% of total traffic.
    """
    weight = 1
    wait_time = between(0.1, 0.5)   # fast — intentionally approaches rate limit

    @task
    def rapid_chat(self):
        with self.client.post(
            CHAT_ENDPOINT,
            json=_chat_payload(),
            headers=_auth_headers(),
            catch_response=True,
            name=f"POST {CHAT_ENDPOINT} [rapid-fire]",
        ) as resp:
            # Both 200 and 429 are expected/correct — this scenario tests
            # that the rate limiter fires correctly, not that requests succeed.
            if resp.status_code in (200, 429, 402):
                resp.success()
            else:
                resp.failure(f"Unexpected {resp.status_code}")


# ── Event hooks ───────────────────────────────────────────────────────────────

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Print configuration at test start."""
    print("\n" + "=" * 60)
    print("Cortex Gateway — Locust Load Test")
    print("=" * 60)
    print(f"Target host:  {environment.host}")
    print(f"Chat model:   {CHAT_MODEL}")
    print(f"API key set:  {'Yes' if API_KEY else 'No — unauthenticated requests'}")
    print("=" * 60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print summary on test stop."""
    stats = environment.stats
    print("\n" + "=" * 60)
    print("Load Test Complete — Summary")
    print("=" * 60)
    print(f"Total requests:    {stats.total.num_requests}")
    print(f"Total failures:    {stats.total.num_failures}")
    print(f"Requests/sec:      {stats.total.current_rps:.2f}")
    print(f"Avg response (ms): {stats.total.avg_response_time:.0f}")
    print(f"p95 response (ms): {stats.total.get_response_time_percentile(0.95):.0f}")
    print(f"p99 response (ms): {stats.total.get_response_time_percentile(0.99):.0f}")
    print("=" * 60 + "\n")
