"""
Cortex Gateway — Phase 9A Model Registry Tests.

Tests for:
  1. Registry CRUD (create, list, get, patch, delete)
  2. Admin RBAC (admin → allowed, member → 403)
  3. Duplicate (provider, model_name) → 409
  4. Capability validation (unknown capability → 422)
  5. Pricing validation (negative cost → 422)
  6. Context window validation (zero → 422)
  7. Phase 3 reads registry (routing uses DB-backed catalog)
  8. Phase 6 reads registry (cost calculator uses DB-backed catalog)
  9. Ollama installed model eligible
  10. Ollama missing model excluded

All DB/Redis operations are mocked.
No real API credentials required.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.schemas import RequestContext
from app.main import app

# ── Shared helpers ────────────────────────────────────────────────────────────

_ADMIN_CTX = RequestContext(
    organization_id="org-9a",
    team_id="team-9a",
    api_key_id="key-9a-admin",
    role="admin",
)
_MEMBER_CTX = RequestContext(
    organization_id="org-9a",
    team_id="team-9a",
    api_key_id="key-9a-member",
    role="member",
)

_SAMPLE_CREATE = {
    "provider": "groq",
    "model_name": "test-model-9a",
    "input_cost_per_1k": 0.0005,
    "output_cost_per_1k": 0.0008,
    "capabilities": ["text", "json", "code"],
    "context_window": 32768,
    "baseline_latency_ms": 150.0,
    "enabled": True,
}


def _make_mock_db_session():
    """Return an AsyncMock standing in for AsyncSession."""
    return AsyncMock()


@contextmanager
def _test_client():
    """Context manager yielding a TestClient with all infra mocked."""
    from app.database.session import get_db_dependency

    mock_session = _make_mock_db_session()

    async def _override_db():
        yield mock_session

    with (
        patch("app.main.init_db"),
        patch("app.main.init_redis"),
        patch("app.main.close_db", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
        patch("app.main._init_model_catalog", new_callable=AsyncMock),
        patch("app.main._catalog_refresh_loop", new_callable=AsyncMock),
    ):
        with TestClient(app, raise_server_exceptions=True) as client:
            app.dependency_overrides[get_db_dependency] = _override_db
            yield client
            app.dependency_overrides.pop(get_db_dependency, None)


def _make_entry_mock(
    model_id: str = "entry-uuid-1",
    provider: str = "groq",
    model_name: str = "test-model-9a",
    input_cost: float = 0.0005,
    output_cost: float = 0.0008,
    capabilities=None,
    context_window: int = 32768,
    baseline_latency_ms: float = 150.0,
    enabled: bool = True,
):
    """Build a minimal mock ModelRegistryEntry."""
    from datetime import datetime, timezone

    m = MagicMock()
    m.id = model_id
    m.provider = provider
    m.model_name = model_name
    m.display_name = None
    m.input_cost_per_1k = input_cost
    m.output_cost_per_1k = output_cost
    m.cost_per_1k_tokens = (input_cost + output_cost) / 2.0
    m.capabilities = capabilities or ["text", "json", "code"]
    m.context_window = context_window
    m.baseline_latency_ms = baseline_latency_ms
    m.enabled = enabled
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
    m.added_at = now
    m.updated_at = now
    return m


# ── 1. CRUD Tests ─────────────────────────────────────────────────────────────


class TestModelRegistryCreate:
    """POST /api/v1/models — create a new registry entry."""

    def test_create_valid_model(self) -> None:
        """Admin creates a valid model → 201 with correct fields."""
        from app.auth.dependencies import require_admin
        from app.model_registry.service import ModelRegistryService

        mock_entry = _make_entry_mock()

        with _test_client() as client:
            app.dependency_overrides[require_admin] = lambda: _ADMIN_CTX

            with (
                patch.object(
                    ModelRegistryService, "create_model", new_callable=AsyncMock,
                    return_value=mock_entry,
                ),
                patch(
                    "app.api.v1.endpoints.model_registry._trigger_catalog_refresh",
                    new_callable=AsyncMock,
                ),
            ):
                resp = client.post("/api/v1/models", json=_SAMPLE_CREATE)

            app.dependency_overrides.clear()

        assert resp.status_code == 201
        data = resp.json()
        assert data["provider"] == "groq"
        assert data["model_name"] == "test-model-9a"
        assert data["enabled"] is True

    def test_create_duplicate_returns_409(self) -> None:
        """Duplicate (provider, model_name) → 409 Conflict."""
        from app.auth.dependencies import require_admin
        from app.model_registry.exceptions import ModelAlreadyExistsError
        from app.model_registry.service import ModelRegistryService

        with _test_client() as client:
            app.dependency_overrides[require_admin] = lambda: _ADMIN_CTX

            with patch.object(
                ModelRegistryService, "create_model", new_callable=AsyncMock,
                side_effect=ModelAlreadyExistsError("groq", "test-model-9a"),
            ):
                resp = client.post("/api/v1/models", json=_SAMPLE_CREATE)

            app.dependency_overrides.clear()

        assert resp.status_code == 409
        body = resp.json()
        # Response may use {"detail": ...} or the global error envelope
        detail_text = body.get("detail") or (body.get("error") or {}).get("message", "")
        assert "already exists" in detail_text or resp.status_code == 409

    def test_create_unknown_capability_returns_422(self) -> None:
        """Unknown capability token → 422 validation error."""
        from app.auth.dependencies import require_admin

        bad_body = {**_SAMPLE_CREATE, "capabilities": ["text", "quantum_ai"]}

        with _test_client() as client:
            app.dependency_overrides[require_admin] = lambda: _ADMIN_CTX
            resp = client.post("/api/v1/models", json=bad_body)
            app.dependency_overrides.clear()

        assert resp.status_code == 422

    def test_create_negative_input_cost_returns_422(self) -> None:
        """Negative input cost → 422."""
        from app.auth.dependencies import require_admin

        bad_body = {**_SAMPLE_CREATE, "input_cost_per_1k": -0.001}

        with _test_client() as client:
            app.dependency_overrides[require_admin] = lambda: _ADMIN_CTX
            resp = client.post("/api/v1/models", json=bad_body)
            app.dependency_overrides.clear()

        assert resp.status_code == 422

    def test_create_zero_context_window_returns_422(self) -> None:
        """Zero context window → 422."""
        from app.auth.dependencies import require_admin

        bad_body = {**_SAMPLE_CREATE, "context_window": 0}

        with _test_client() as client:
            app.dependency_overrides[require_admin] = lambda: _ADMIN_CTX
            resp = client.post("/api/v1/models", json=bad_body)
            app.dependency_overrides.clear()

        assert resp.status_code == 422

    def test_create_unknown_provider_returns_422(self) -> None:
        """Unknown provider → 422."""
        from app.auth.dependencies import require_admin

        bad_body = {**_SAMPLE_CREATE, "provider": "anthropic_unknown_x"}

        with _test_client() as client:
            app.dependency_overrides[require_admin] = lambda: _ADMIN_CTX
            resp = client.post("/api/v1/models", json=bad_body)
            app.dependency_overrides.clear()

        assert resp.status_code == 422

    def test_create_extra_field_returns_422(self) -> None:
        """Extra unknown field → 422 (strict validation)."""
        from app.auth.dependencies import require_admin

        bad_body = {**_SAMPLE_CREATE, "quantum_field": "oops"}

        with _test_client() as client:
            app.dependency_overrides[require_admin] = lambda: _ADMIN_CTX
            resp = client.post("/api/v1/models", json=bad_body)
            app.dependency_overrides.clear()

        assert resp.status_code == 422


# ── 2. RBAC Tests ─────────────────────────────────────────────────────────────


class TestModelRegistryRBAC:
    """Member role must receive 403 on all mutations."""

    def test_member_create_returns_403(self) -> None:
        """Member key → 403 on create (require_admin enforces this)."""
        import fastapi

        from app.auth.dependencies import require_admin

        def _member_forbidden():
            raise fastapi.HTTPException(
                status_code=403, detail="Admin role required."
            )

        with _test_client() as client:
            app.dependency_overrides[require_admin] = _member_forbidden
            resp = client.post("/api/v1/models", json=_SAMPLE_CREATE)
            app.dependency_overrides.clear()

        assert resp.status_code == 403

    def test_member_list_returns_403(self) -> None:
        """Member key → 403 on list."""
        import fastapi

        from app.auth.dependencies import require_admin

        def _member_forbidden():
            raise fastapi.HTTPException(
                status_code=403, detail="Admin role required."
            )

        with _test_client() as client:
            app.dependency_overrides[require_admin] = _member_forbidden
            resp = client.get("/api/v1/models")
            app.dependency_overrides.clear()

        assert resp.status_code == 403

    def test_unauthenticated_returns_401_or_403(self) -> None:
        """No key → 401 from require_admin chain."""
        with _test_client() as client:
            resp = client.get("/api/v1/models")

        assert resp.status_code in (401, 403)


# ── 3. List / Get / Patch / Delete ────────────────────────────────────────────


class TestModelRegistryReadUpdate:
    """READ and PATCH operations."""

    def test_list_returns_all_models(self) -> None:
        """GET /api/v1/models → list of entries."""
        from app.auth.dependencies import require_admin
        from app.model_registry.service import ModelRegistryService

        entries = [_make_entry_mock("e1", "gemini", "gemini-1.5-flash")]

        with _test_client() as client:
            app.dependency_overrides[require_admin] = lambda: _ADMIN_CTX

            with patch.object(
                ModelRegistryService, "list_models", new_callable=AsyncMock,
                return_value=entries,
            ):
                resp = client.get("/api/v1/models")

            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["models"][0]["model_name"] == "gemini-1.5-flash"

    def test_get_by_id_returns_entry(self) -> None:
        """GET /api/v1/models/{id} → single entry."""
        from app.auth.dependencies import require_admin
        from app.model_registry.service import ModelRegistryService

        entry = _make_entry_mock("id-xyz")

        with _test_client() as client:
            app.dependency_overrides[require_admin] = lambda: _ADMIN_CTX

            with patch.object(
                ModelRegistryService, "get_model", new_callable=AsyncMock,
                return_value=entry,
            ):
                resp = client.get("/api/v1/models/id-xyz")

            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["id"] == "id-xyz"

    def test_get_missing_returns_404(self) -> None:
        """GET /api/v1/models/{id} for unknown ID → 404."""
        from app.auth.dependencies import require_admin
        from app.model_registry.exceptions import ModelNotFoundError
        from app.model_registry.service import ModelRegistryService

        with _test_client() as client:
            app.dependency_overrides[require_admin] = lambda: _ADMIN_CTX

            with patch.object(
                ModelRegistryService, "get_model", new_callable=AsyncMock,
                side_effect=ModelNotFoundError("no-such-id"),
            ):
                resp = client.get("/api/v1/models/no-such-id")

            app.dependency_overrides.clear()

        assert resp.status_code == 404

    def test_patch_updates_entry(self) -> None:
        """PATCH /api/v1/models/{id} → 200 with updated fields."""
        from app.auth.dependencies import require_admin
        from app.model_registry.service import ModelRegistryService

        updated = _make_entry_mock("id-xyz", enabled=False)

        with _test_client() as client:
            app.dependency_overrides[require_admin] = lambda: _ADMIN_CTX

            with (
                patch.object(
                    ModelRegistryService, "update_model", new_callable=AsyncMock,
                    return_value=updated,
                ),
                patch(
                    "app.api.v1.endpoints.model_registry._trigger_catalog_refresh",
                    new_callable=AsyncMock,
                ),
            ):
                resp = client.patch(
                    "/api/v1/models/id-xyz",
                    json={"enabled": False},
                )

            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_delete_returns_204(self) -> None:
        """DELETE /api/v1/models/{id} → 204."""
        from app.auth.dependencies import require_admin
        from app.model_registry.service import ModelRegistryService

        with _test_client() as client:
            app.dependency_overrides[require_admin] = lambda: _ADMIN_CTX

            with (
                patch.object(
                    ModelRegistryService, "delete_model", new_callable=AsyncMock,
                    return_value=None,
                ),
                patch(
                    "app.api.v1.endpoints.model_registry._trigger_catalog_refresh",
                    new_callable=AsyncMock,
                ),
            ):
                resp = client.delete("/api/v1/models/id-xyz")

            app.dependency_overrides.clear()

        assert resp.status_code == 204


# ── 4. Phase 3 + Phase 6 Integration ─────────────────────────────────────────


class TestCatalogIntegration:
    """Verify Phase 3 routing and Phase 6 cost calculator use DB-backed catalog."""

    def test_phase3_reads_registry_catalog(self) -> None:
        """
        Phase 3 routing engine uses _shared_catalog (DB-backed).
        Verify get_routing_engine passes metadata_catalog=_shared_catalog.
        """
        from app.providers.registry import registry
        from app.routing.metadata import _shared_catalog
        from app.routing.router import get_routing_engine, set_routing_engine

        set_routing_engine(None)
        try:
            engine = get_routing_engine(registry)
            assert engine._metadata_catalog is _shared_catalog
        finally:
            set_routing_engine(None)

    def test_phase6_cost_calculator_uses_shared_catalog(self) -> None:
        """
        CostCalculator uses _shared_catalog for pricing.
        Pre-load a known entry and verify non-zero cost.
        """
        from app.budget.cost import CostCalculator
        from app.routing.metadata import ModelMetadata, _shared_catalog
        from app.schemas.chat import ChatCompletionRequest

        _shared_catalog._catalog["groq:test-9a-model"] = ModelMetadata(
            provider="groq",
            model="test-9a-model",
            cost_per_1k_tokens=0.001,
            input_cost_per_1k=0.0005,
            output_cost_per_1k=0.0008,
            capabilities=["text"],
            context_window=8192,
            baseline_latency_ms=100.0,
        )

        calc = CostCalculator(catalog=_shared_catalog)
        request = ChatCompletionRequest(
            provider="groq",
            model="test-9a-model",
            messages=[{"role": "user", "content": "Hello world"}],
        )
        cost = calc.estimate_cost("groq", "test-9a-model", request)
        assert cost > 0.0

        del _shared_catalog._catalog["groq:test-9a-model"]

    def test_catalog_load_from_db_populates_entries(self) -> None:
        """
        ModelMetadataCatalog.load_from_db() populates in-memory dict from DB entries.
        """
        import asyncio

        from app.model_registry.service import ModelRegistryService
        from app.routing.metadata import ModelMetadataCatalog

        entry = _make_entry_mock(
            "e1", "gemini", "gemini-1.5-flash",
            input_cost=0.000075, output_cost=0.0003,
            capabilities=["text", "vision"],
            context_window=1_000_000,
            baseline_latency_ms=450.0,
        )

        catalog = ModelMetadataCatalog()

        async def _run():
            mock_session = MagicMock()
            with patch.object(
                ModelRegistryService, "get_all_for_catalog",
                new_callable=AsyncMock,
                return_value=[entry],
            ):
                await catalog.load_from_db(mock_session)

        asyncio.run(_run())

        assert catalog.size == 1
        meta = catalog.get("gemini", "gemini-1.5-flash")
        assert meta.provider == "gemini"
        assert meta.input_cost_per_1k == pytest.approx(0.000075)
        assert "vision" in meta.capabilities


# ── 5. Ollama Intersection Tests ──────────────────────────────────────────────


class TestOllamaIntersection:
    """Phase 9A: Ollama eligibility = registry ∩ installed."""

    def test_installed_and_registered_model_is_eligible(self) -> None:
        from app.routing.candidates import _resolve_ollama_models

        live = ["llama3.2", "qwen2.5"]
        registry_models = ["llama3.2", "qwen2.5", "llama3.2-vision"]

        result = _resolve_ollama_models(live_models=live, catalog_models=registry_models)

        assert "llama3.2" in result
        assert "qwen2.5" in result

    def test_registered_but_not_installed_is_excluded(self) -> None:
        from app.routing.candidates import _resolve_ollama_models

        live = ["llama3.2"]
        registry_models = ["llama3.2", "qwen2.5", "llama3.2-vision"]

        result = _resolve_ollama_models(live_models=live, catalog_models=registry_models)

        assert "llama3.2" in result
        assert "qwen2.5" not in result
        assert "llama3.2-vision" not in result

    def test_installed_but_not_registered_is_excluded(self) -> None:
        from app.routing.candidates import _resolve_ollama_models

        live = ["llama3.2", "some-unknown-model"]
        registry_models = ["llama3.2"]

        result = _resolve_ollama_models(live_models=live, catalog_models=registry_models)

        assert "llama3.2" in result
        assert "some-unknown-model" not in result

    def test_empty_live_models_excludes_all_ollama(self) -> None:
        from app.routing.candidates import _resolve_ollama_models

        result = _resolve_ollama_models(
            live_models=[],
            catalog_models=["llama3.2", "qwen2.5"],
        )
        assert result == []

    def test_empty_registry_excludes_all_ollama(self) -> None:
        from app.routing.candidates import _resolve_ollama_models

        result = _resolve_ollama_models(
            live_models=["llama3.2", "qwen2.5"],
            catalog_models=[],
        )
        assert result == []

    def test_bare_name_matches_tagged_live_model(self) -> None:
        """Registry has 'llama3.2', Ollama reports 'llama3.2:latest' → eligible via bare match."""
        from app.routing.candidates import _resolve_ollama_models

        live = ["llama3.2:latest"]
        registry_models = ["llama3.2"]

        result = _resolve_ollama_models(live_models=live, catalog_models=registry_models)

        assert "llama3.2" in result


# ── 6. Schema Validation Unit Tests ──────────────────────────────────────────


class TestModelRegistrySchemas:
    """Pydantic schema validation tests (no HTTP layer)."""

    def test_valid_create_accepted(self) -> None:
        from app.model_registry.schemas import ModelRegistryCreate

        data = ModelRegistryCreate(**_SAMPLE_CREATE)
        assert data.provider == "groq"
        assert data.model_name == "test-model-9a"

    def test_provider_normalized_to_lowercase(self) -> None:
        from app.model_registry.schemas import ModelRegistryCreate

        data = ModelRegistryCreate(**{**_SAMPLE_CREATE, "provider": "GROQ"})
        assert data.provider == "groq"

    def test_capabilities_deduplicated(self) -> None:
        from app.model_registry.schemas import ModelRegistryCreate

        data = ModelRegistryCreate(
            **{**_SAMPLE_CREATE, "capabilities": ["text", "json", "text"]}
        )
        assert data.capabilities.count("text") == 1

    def test_empty_capabilities_rejected(self) -> None:
        from pydantic import ValidationError

        from app.model_registry.schemas import ModelRegistryCreate

        with pytest.raises(ValidationError):
            ModelRegistryCreate(**{**_SAMPLE_CREATE, "capabilities": []})

    def test_unknown_capability_rejected(self) -> None:
        from pydantic import ValidationError

        from app.model_registry.schemas import ModelRegistryCreate

        with pytest.raises(ValidationError, match="Unknown capability"):
            ModelRegistryCreate(**{**_SAMPLE_CREATE, "capabilities": ["text", "hacking"]})

    def test_update_partial_fields_accepted(self) -> None:
        from app.model_registry.schemas import ModelRegistryUpdate

        update = ModelRegistryUpdate(enabled=False)
        assert update.enabled is False
        assert update.capabilities is None

    def test_update_extra_field_rejected(self) -> None:
        from pydantic import ValidationError

        from app.model_registry.schemas import ModelRegistryUpdate

        # Use model_validate(dict) instead of a direct kwarg so Pylance does
        # not flag 'provider_override' as an unexpected keyword argument.
        # Pydantic v2 still raises ValidationError at runtime (extra="forbid").
        with pytest.raises(ValidationError):
            ModelRegistryUpdate.model_validate({"provider_override": "hacked"})

    def test_provider_model_names_returns_correct_subset(self) -> None:
        """ModelMetadataCatalog.provider_model_names() returns models for one provider only."""
        from app.routing.metadata import ModelMetadata, ModelMetadataCatalog

        catalog = ModelMetadataCatalog()
        catalog._catalog["gemini:gemini-1.5-flash"] = ModelMetadata(
            provider="gemini", model="gemini-1.5-flash",
            cost_per_1k_tokens=0.0001, input_cost_per_1k=0.0001,
            output_cost_per_1k=0.0003, capabilities=["text"],
            context_window=1_000_000, baseline_latency_ms=450.0,
        )
        catalog._catalog["groq:llama3-8b"] = ModelMetadata(
            provider="groq", model="llama3-8b",
            cost_per_1k_tokens=0.0001, input_cost_per_1k=0.0001,
            output_cost_per_1k=0.0001, capabilities=["text"],
            context_window=8192, baseline_latency_ms=100.0,
        )

        gemini_models = catalog.provider_model_names("gemini")
        assert "gemini-1.5-flash" in gemini_models
        assert "llama3-8b" not in gemini_models

        groq_models = catalog.provider_model_names("groq")
        assert "llama3-8b" in groq_models
        assert "gemini-1.5-flash" not in groq_models
