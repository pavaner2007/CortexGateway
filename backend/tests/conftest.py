"""
Cortex Gateway — Test Configuration and Fixtures.

Provides:
- ``client``         : HTTPX TestClient wrapping the FastAPI app.
- ``mock_db_up``     : Patches check_db_health to return "connected".
- ``mock_db_down``   : Patches check_db_health to return "disconnected".
- ``mock_redis_up``  : Patches check_redis_health to return "connected".
- ``mock_redis_down``: Patches check_redis_health to return "disconnected".

These fixtures run without any external Docker services.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    """
    Session-scoped synchronous TestClient.

    ``TestClient`` manages the ASGI lifespan automatically.
    We skip the real DB/Redis init by patching them at module level.
    """
    # Patch init_db and init_redis so the lifespan startup does not attempt
    # real network connections during tests.
    # Phase 9A: also patch catalog init + refresh loop.
    # Phase 9B: also patch _semantic_cache initialization.
    # Phase 9C: also patch PolicyResolver.resolve to return global default.
    from app.policy.schemas import GLOBAL_DEFAULT_POLICY

    _resolve_mock = AsyncMock(return_value=GLOBAL_DEFAULT_POLICY)
    with (
        patch("app.main.init_db"),
        patch("app.main.init_redis"),
        patch("app.main.close_db", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
        patch("app.main._init_model_catalog", new_callable=AsyncMock),
        patch("app.main._catalog_refresh_loop", new_callable=AsyncMock),
        patch("app.main.build_semantic_cache", return_value=None),
        patch("app.policy.resolver.PolicyResolver.resolve", new=_resolve_mock),
    ):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


@pytest.fixture(autouse=True, scope="session")
def _patch_catalog_for_all_tests():
    """
    Ensure _init_model_catalog and _catalog_refresh_loop are always no-ops
    in every test that creates its own TestClient (not using the session client).

    This prevents asyncio and DB errors from the Phase 9A startup additions.
    """
    with (
        patch("app.main._init_model_catalog", new_callable=AsyncMock),
        patch("app.main._catalog_refresh_loop", new_callable=AsyncMock),
    ):
        yield


@pytest.fixture(autouse=True, scope="session")
def _seed_shared_catalog():
    """
    Phase 9A: Pre-populate _shared_catalog with the same 15-entry dataset
    that the static _DEFAULT_CATALOG held. This ensures routing, scoring, and
    cost tests work without a DB connection.

    The seed data is injected directly into the in-memory dict so no DB or
    async operations are required. Tests that need to test catalog loading
    from DB should use their own fresh ModelMetadataCatalog() instance.
    """
    from app.routing.metadata import ModelMetadata, _shared_catalog

    _seed = {
        # Gemini
        "gemini:gemini-1.5-flash": ModelMetadata(
            provider="gemini", model="gemini-1.5-flash",
            cost_per_1k_tokens=0.0001875, input_cost_per_1k=0.000075, output_cost_per_1k=0.000300,
            capabilities=["text", "vision", "json", "code"],
            context_window=1_000_000, baseline_latency_ms=450.0,
        ),
        "gemini:gemini-1.5-pro": ModelMetadata(
            provider="gemini", model="gemini-1.5-pro",
            cost_per_1k_tokens=0.003125, input_cost_per_1k=0.001250, output_cost_per_1k=0.005000,
            capabilities=["text", "vision", "json", "code", "complex_reasoning"],
            context_window=2_000_000, baseline_latency_ms=900.0,
        ),
        "gemini:gemini-2.0-flash": ModelMetadata(
            provider="gemini", model="gemini-2.0-flash",
            cost_per_1k_tokens=0.000250, input_cost_per_1k=0.000100, output_cost_per_1k=0.000400,
            capabilities=["text", "vision", "json", "code", "tools"],
            context_window=1_000_000, baseline_latency_ms=350.0,
        ),
        "gemini:gemini-2.5-flash": ModelMetadata(
            provider="gemini", model="gemini-2.5-flash",
            cost_per_1k_tokens=0.000250, input_cost_per_1k=0.000100, output_cost_per_1k=0.000400,
            capabilities=["text", "vision", "json", "code", "tools"],
            context_window=1_000_000, baseline_latency_ms=350.0,
        ),
        # Groq
        "groq:llama-3.3-70b-versatile": ModelMetadata(
            provider="groq", model="llama-3.3-70b-versatile",
            cost_per_1k_tokens=0.000690, input_cost_per_1k=0.000590, output_cost_per_1k=0.000790,
            capabilities=["text", "json", "code", "tools"],
            context_window=128_000, baseline_latency_ms=180.0,
        ),
        "groq:llama-3.1-8b-instant": ModelMetadata(
            provider="groq", model="llama-3.1-8b-instant",
            cost_per_1k_tokens=0.000065, input_cost_per_1k=0.000050, output_cost_per_1k=0.000080,
            capabilities=["text", "json", "code"],
            context_window=128_000, baseline_latency_ms=90.0,
        ),
        "groq:llama3-8b-8192": ModelMetadata(
            provider="groq", model="llama3-8b-8192",
            cost_per_1k_tokens=0.000065, input_cost_per_1k=0.000050, output_cost_per_1k=0.000080,
            capabilities=["text", "json", "code"],
            context_window=8192, baseline_latency_ms=100.0,
        ),
        "groq:llama3-70b-8192": ModelMetadata(
            provider="groq", model="llama3-70b-8192",
            cost_per_1k_tokens=0.000690, input_cost_per_1k=0.000590, output_cost_per_1k=0.000790,
            capabilities=["text", "json", "code", "tools"],
            context_window=8192, baseline_latency_ms=220.0,
        ),
        "groq:mixtral-8x7b-32768": ModelMetadata(
            provider="groq", model="mixtral-8x7b-32768",
            cost_per_1k_tokens=0.000240, input_cost_per_1k=0.000240, output_cost_per_1k=0.000240,
            capabilities=["text", "json", "code"],
            context_window=32768, baseline_latency_ms=150.0,
        ),
        "groq:gemma2-9b-it": ModelMetadata(
            provider="groq", model="gemma2-9b-it",
            cost_per_1k_tokens=0.000100, input_cost_per_1k=0.000100, output_cost_per_1k=0.000100,
            capabilities=["text", "code"],
            context_window=8192, baseline_latency_ms=130.0,
        ),
        # Ollama
        "ollama:llama3.2": ModelMetadata(
            provider="ollama", model="llama3.2",
            cost_per_1k_tokens=0.0, input_cost_per_1k=0.0, output_cost_per_1k=0.0,
            capabilities=["text", "json", "code"],
            context_window=8192, baseline_latency_ms=300.0,
        ),
        "ollama:llama3.2:latest": ModelMetadata(
            provider="ollama", model="llama3.2:latest",
            cost_per_1k_tokens=0.0, input_cost_per_1k=0.0, output_cost_per_1k=0.0,
            capabilities=["text", "json", "code"],
            context_window=8192, baseline_latency_ms=300.0,
        ),
        "ollama:llama3.2-vision": ModelMetadata(
            provider="ollama", model="llama3.2-vision",
            cost_per_1k_tokens=0.0, input_cost_per_1k=0.0, output_cost_per_1k=0.0,
            capabilities=["text", "vision", "code"],
            context_window=8192, baseline_latency_ms=450.0,
        ),
        "ollama:qwen2.5": ModelMetadata(
            provider="ollama", model="qwen2.5",
            cost_per_1k_tokens=0.0, input_cost_per_1k=0.0, output_cost_per_1k=0.0,
            capabilities=["text", "json", "code"],
            context_window=32768, baseline_latency_ms=280.0,
        ),
        "ollama:qwen2.5:latest": ModelMetadata(
            provider="ollama", model="qwen2.5:latest",
            cost_per_1k_tokens=0.0, input_cost_per_1k=0.0, output_cost_per_1k=0.0,
            capabilities=["text", "json", "code"],
            context_window=32768, baseline_latency_ms=280.0,
        ),
        "ollama:llava": ModelMetadata(
            provider="ollama", model="llava",
            cost_per_1k_tokens=0.0, input_cost_per_1k=0.0, output_cost_per_1k=0.0,
            capabilities=["text", "vision", "code"],
            context_window=4096, baseline_latency_ms=500.0,
        ),
        "ollama:llava:latest": ModelMetadata(
            provider="ollama", model="llava:latest",
            cost_per_1k_tokens=0.0, input_cost_per_1k=0.0, output_cost_per_1k=0.0,
            capabilities=["text", "vision", "code"],
            context_window=4096, baseline_latency_ms=500.0,
        ),
        # Additional entries for budget downgrade tests
        "ollama:qwen2.5-coder": ModelMetadata(
            provider="ollama", model="qwen2.5-coder",
            cost_per_1k_tokens=0.0, input_cost_per_1k=0.0, output_cost_per_1k=0.0,
            capabilities=["text", "code"],
            context_window=32768, baseline_latency_ms=200.0,
        ),
        "gemini:gemini-flash-textonly": ModelMetadata(
            provider="gemini", model="gemini-flash-textonly",
            cost_per_1k_tokens=0.00001, input_cost_per_1k=0.00001, output_cost_per_1k=0.00001,
            capabilities=["text"],
            context_window=128000, baseline_latency_ms=80.0,
        ),
        "gemini:gemini-1.5-pro": ModelMetadata(
            provider="gemini", model="gemini-1.5-pro",
            cost_per_1k_tokens=0.003125, input_cost_per_1k=0.001250, output_cost_per_1k=0.005000,
            capabilities=["text", "vision", "json", "code", "complex_reasoning"],
            context_window=2_000_000, baseline_latency_ms=900.0,
        ),
    }

    # Inject into shared catalog
    _shared_catalog._catalog.update(_seed)
    yield
    # Clean up after session to leave no side effects
    for key in _seed:
        _shared_catalog._catalog.pop(key, None)


@pytest.fixture()
def mock_db_up():
    """Simulate a healthy PostgreSQL connection."""
    with patch(
        "app.api.v1.endpoints.health.check_db_health",
        new_callable=AsyncMock,
        return_value="connected",
    ):
        yield


@pytest.fixture()
def mock_db_down():
    """Simulate an unreachable PostgreSQL."""
    with patch(
        "app.api.v1.endpoints.health.check_db_health",
        new_callable=AsyncMock,
        return_value="disconnected",
    ):
        yield


@pytest.fixture()
def mock_redis_up():
    """Simulate a healthy Redis connection."""
    with patch(
        "app.api.v1.endpoints.health.check_redis_health",
        new_callable=AsyncMock,
        return_value="connected",
    ):
        yield


@pytest.fixture()
def mock_redis_down():
    """Simulate an unreachable Redis."""
    with patch(
        "app.api.v1.endpoints.health.check_redis_health",
        new_callable=AsyncMock,
        return_value="disconnected",
    ):
        yield
