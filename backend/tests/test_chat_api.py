"""
Cortex Gateway — Phase 2 API Endpoint Tests.

Tests all Phase 2 HTTP endpoints:
    POST /api/v1/chat/completions
    GET  /api/v1/providers
    GET  /api/v1/providers/{provider}
    GET  /api/v1/providers/{provider}/models

All provider adapters are mocked — no real API credentials required.
All Phase 1 endpoints continue to be tested in test_endpoints.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.providers.exceptions import (
    InvalidProviderError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.providers.registry import ProviderRegistry
from app.schemas.chat import (
    ChatCompletionChoice,
    ChatCompletionResponse,
    ChatMessageResponse,
    ModelListResponse,
    ProviderInfo,
    ProviderListResponse,
    ResponseMetadata,
    UsageMetadata,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_mock_response(
    provider: str = "groq",
    model: str = "llama-3.3-70b-versatile",
    content: str = "Test response",
    request_id: str = "test-req-id",
) -> ChatCompletionResponse:
    return ChatCompletionResponse(
        provider=provider,
        model=model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessageResponse(content=content),
                finish_reason="stop",
            )
        ],
        usage=UsageMetadata(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        metadata=ResponseMetadata(request_id=request_id, latency_ms=150.0),
    )


def _make_mock_registry(
    providers: list[str] | None = None,
) -> ProviderRegistry:
    """Build a mock registry with mock providers."""
    reg = ProviderRegistry()
    for name in (providers or ["groq", "gemini", "ollama"]):
        mp = MagicMock()
        mp.name = name
        mp.chat = AsyncMock(
            side_effect=lambda req, req_id, p=name: _make_mock_response(
                provider=p, model=req.model, request_id=req_id
            )
        )
        mp.list_models = AsyncMock(return_value=[f"{name}-model-1", f"{name}-model-2"])
        mp.health_check = AsyncMock(return_value=True)
        reg.register(mp)
    return reg


from app.providers.registry import get_registry


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Session-scoped test client with mocked infrastructure and providers."""
    mock_registry = _make_mock_registry()
    with (
        patch("app.main.init_db"),
        patch("app.main.init_redis"),
        patch("app.main.close_db", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
        patch("app.main._init_providers"),
    ):
        app.dependency_overrides[get_registry] = lambda: mock_registry
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
        app.dependency_overrides.clear()


# ── Phase 1 endpoints still work ─────────────────────────────────────────────


class TestPhase1EndpointsUnchanged:
    def test_root_still_works(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_version_still_works(self, client: TestClient) -> None:
        resp = client.get("/version")
        assert resp.status_code == 200
        assert "version" in resp.json()

    def test_docs_still_works(self, client: TestClient) -> None:
        resp = client.get("/docs")
        assert resp.status_code == 200

    def test_redoc_still_works(self, client: TestClient) -> None:
        resp = client.get("/redoc")
        assert resp.status_code == 200


# ── POST /api/v1/chat/completions ─────────────────────────────────────────────


class TestChatCompletionsEndpoint:
    def _payload(
        self,
        provider: str = "groq",
        model: str = "llama-3.3-70b-versatile",
        content: str = "Explain Docker",
    ) -> dict:
        return {
            "provider": provider,
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.7,
            "max_tokens": 500,
        }

    def test_returns_200_for_valid_request(self, client: TestClient) -> None:
        mock_reg = _make_mock_registry()
        with patch("app.api.v1.endpoints.chat.get_registry", return_value=mock_reg):
            resp = client.post("/api/v1/chat/completions", json=self._payload())
        assert resp.status_code == 200

    def test_response_has_required_fields(self, client: TestClient) -> None:
        mock_reg = _make_mock_registry()
        with patch("app.api.v1.endpoints.chat.get_registry", return_value=mock_reg):
            resp = client.post("/api/v1/chat/completions", json=self._payload())
        data = resp.json()
        assert "id" in data
        assert "provider" in data
        assert "model" in data
        assert "choices" in data
        assert "usage" in data
        assert "metadata" in data

    def test_response_id_has_ctx_prefix(self, client: TestClient) -> None:
        mock_reg = _make_mock_registry()
        with patch("app.api.v1.endpoints.chat.get_registry", return_value=mock_reg):
            resp = client.post("/api/v1/chat/completions", json=self._payload())
        assert resp.json()["id"].startswith("ctx_")

    def test_response_object_is_chat_completion(self, client: TestClient) -> None:
        mock_reg = _make_mock_registry()
        with patch("app.api.v1.endpoints.chat.get_registry", return_value=mock_reg):
            resp = client.post("/api/v1/chat/completions", json=self._payload())
        assert resp.json()["object"] == "chat.completion"

    def test_metadata_has_request_id(self, client: TestClient) -> None:
        mock_reg = _make_mock_registry()
        with patch("app.api.v1.endpoints.chat.get_registry", return_value=mock_reg):
            resp = client.post(
                "/api/v1/chat/completions",
                json=self._payload(),
                headers={"X-Request-ID": "my-test-id"},
            )
        assert "metadata" in resp.json()
        assert "request_id" in resp.json()["metadata"]

    def test_metadata_has_latency_ms(self, client: TestClient) -> None:
        mock_reg = _make_mock_registry()
        with patch("app.api.v1.endpoints.chat.get_registry", return_value=mock_reg):
            resp = client.post("/api/v1/chat/completions", json=self._payload())
        assert "latency_ms" in resp.json()["metadata"]

    def test_usage_fields_present(self, client: TestClient) -> None:
        mock_reg = _make_mock_registry()
        with patch("app.api.v1.endpoints.chat.get_registry", return_value=mock_reg):
            resp = client.post("/api/v1/chat/completions", json=self._payload())
        usage = resp.json()["usage"]
        assert "prompt_tokens" in usage
        assert "completion_tokens" in usage
        assert "total_tokens" in usage

    def test_x_request_id_header_in_response(self, client: TestClient) -> None:
        """X-Request-ID header is returned on every response."""
        mock_reg = _make_mock_registry()
        with patch("app.api.v1.endpoints.chat.get_registry", return_value=mock_reg):
            resp = client.post("/api/v1/chat/completions", json=self._payload())
        assert "x-request-id" in resp.headers

    def test_invalid_provider_returns_404(self, client: TestClient) -> None:
        empty_reg = ProviderRegistry()
        app.dependency_overrides[get_registry] = lambda: empty_reg
        try:
            resp = client.post(
                "/api/v1/chat/completions",
                json={**self._payload(), "provider": "nonexistent"},
            )
        finally:
            app.dependency_overrides[get_registry] = lambda: _make_mock_registry()
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "INVALID_PROVIDER"

    def test_invalid_provider_does_not_expose_internals(self, client: TestClient) -> None:
        """Error response never exposes stack traces or internal details."""
        empty_reg = ProviderRegistry()
        app.dependency_overrides[get_registry] = lambda: empty_reg
        try:
            resp = client.post(
                "/api/v1/chat/completions",
                json={**self._payload(), "provider": "badprovider"},
            )
        finally:
            app.dependency_overrides[get_registry] = lambda: _make_mock_registry()
        body = resp.json()
        assert "traceback" not in str(body).lower()
        assert "api_key" not in str(body).lower()

    def _with_error_registry(self, error: Exception) -> ProviderRegistry:
        """Build a registry whose groq provider raises the given error."""
        mock_reg = ProviderRegistry()
        mp = MagicMock()
        mp.name = "groq"
        mp.chat = AsyncMock(side_effect=error)
        mock_reg.register(mp)
        return mock_reg

    def test_provider_timeout_returns_504(self, client: TestClient) -> None:
        """ProviderTimeoutError produces HTTP 504."""
        app.dependency_overrides[get_registry] = lambda: self._with_error_registry(
            ProviderTimeoutError("Timed out")
        )
        try:
            resp = client.post("/api/v1/chat/completions", json=self._payload())
        finally:
            app.dependency_overrides[get_registry] = lambda: _make_mock_registry()
        assert resp.status_code == 504
        assert resp.json()["error"]["code"] == "PROVIDER_TIMEOUT"

    def test_provider_rate_limit_returns_429(self, client: TestClient) -> None:
        """ProviderRateLimitError produces HTTP 429."""
        app.dependency_overrides[get_registry] = lambda: self._with_error_registry(
            ProviderRateLimitError("Rate limited")
        )
        try:
            resp = client.post("/api/v1/chat/completions", json=self._payload())
        finally:
            app.dependency_overrides[get_registry] = lambda: _make_mock_registry()
        assert resp.status_code == 429
        assert resp.json()["error"]["code"] == "PROVIDER_RATE_LIMITED"

    def test_provider_auth_error_returns_502(self, client: TestClient) -> None:
        """ProviderAuthError produces HTTP 502."""
        app.dependency_overrides[get_registry] = lambda: self._with_error_registry(
            ProviderAuthError("Auth failed")
        )
        try:
            resp = client.post("/api/v1/chat/completions", json=self._payload())
        finally:
            app.dependency_overrides[get_registry] = lambda: _make_mock_registry()
        assert resp.status_code == 502
        assert resp.json()["error"]["code"] == "PROVIDER_AUTHENTICATION_FAILED"

    def test_provider_unavailable_returns_503(self, client: TestClient) -> None:
        """ProviderUnavailableError produces HTTP 503."""
        app.dependency_overrides[get_registry] = lambda: self._with_error_registry(
            ProviderUnavailableError("Unavailable")
        )
        try:
            resp = client.post("/api/v1/chat/completions", json=self._payload())
        finally:
            app.dependency_overrides[get_registry] = lambda: _make_mock_registry()
        assert resp.status_code == 503

    def test_empty_messages_returns_422(self, client: TestClient) -> None:
        """Empty messages list returns HTTP 422 validation error."""
        resp = client.post(
            "/api/v1/chat/completions",
            json={**self._payload(), "messages": []},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_invalid_role_returns_422(self, client: TestClient) -> None:
        """Invalid message role returns HTTP 422."""
        resp = client.post(
            "/api/v1/chat/completions",
            json={
                **self._payload(),
                "messages": [{"role": "robot", "content": "Hello"}],
            },
        )
        assert resp.status_code == 422

    def test_temperature_out_of_range_returns_422(self, client: TestClient) -> None:
        """temperature > 2.0 returns HTTP 422."""
        resp = client.post(
            "/api/v1/chat/completions",
            json={**self._payload(), "temperature": 5.0},
        )
        assert resp.status_code == 422

    def test_max_tokens_zero_returns_422(self, client: TestClient) -> None:
        """max_tokens=0 returns HTTP 422."""
        resp = client.post(
            "/api/v1/chat/completions",
            json={**self._payload(), "max_tokens": 0},
        )
        assert resp.status_code == 422

    def test_system_message_accepted(self, client: TestClient) -> None:
        """System role is a valid message role."""
        mock_reg = _make_mock_registry()
        with patch("app.api.v1.endpoints.chat.get_registry", return_value=mock_reg):
            resp = client.post(
                "/api/v1/chat/completions",
                json={
                    **self._payload(),
                    "messages": [
                        {"role": "system", "content": "You are helpful."},
                        {"role": "user", "content": "Hi"},
                    ],
                },
            )
        assert resp.status_code == 200

    def test_ollama_chat_completion_success(self, client: TestClient) -> None:
        """POST /api/v1/chat/completions with provider=ollama succeeds."""
        mock_reg = _make_mock_registry(["ollama"])
        with patch("app.api.v1.endpoints.chat.get_registry", return_value=mock_reg):
            resp = client.post(
                "/api/v1/chat/completions",
                json=self._payload(provider="ollama", model="llama3.2"),
            )
        assert resp.status_code == 200
        assert resp.json()["provider"] == "ollama"
        assert resp.json()["model"] == "llama3.2"


# ── GET /api/v1/providers ─────────────────────────────────────────────────────


class TestProvidersListEndpoint:
    def test_returns_200(self, client: TestClient) -> None:
        mock_reg = _make_mock_registry()
        with patch("app.api.v1.endpoints.providers.get_registry", return_value=mock_reg):
            resp = client.get("/api/v1/providers")
        assert resp.status_code == 200

    def test_returns_providers_list(self, client: TestClient) -> None:
        mock_reg = _make_mock_registry(["groq", "ollama"])
        with patch("app.api.v1.endpoints.providers.get_registry", return_value=mock_reg):
            resp = client.get("/api/v1/providers")
        data = resp.json()
        assert "providers" in data
        names = {p["name"] for p in data["providers"]}
        assert "groq" in names
        assert "ollama" in names

    def test_no_api_keys_in_response(self, client: TestClient) -> None:
        """Provider list never exposes API keys."""
        mock_reg = _make_mock_registry()
        with patch("app.api.v1.endpoints.providers.get_registry", return_value=mock_reg):
            resp = client.get("/api/v1/providers")
        assert "api_key" not in str(resp.json()).lower()

    def test_empty_registry_returns_empty_list(self, client: TestClient) -> None:
        empty_reg = ProviderRegistry()
        app.dependency_overrides[get_registry] = lambda: empty_reg
        try:
            resp = client.get("/api/v1/providers")
        finally:
            app.dependency_overrides[get_registry] = lambda: _make_mock_registry()
        assert resp.status_code == 200
        assert resp.json()["providers"] == []


# ── GET /api/v1/providers/{provider} ─────────────────────────────────────────


class TestProviderDetailEndpoint:
    def test_returns_200_for_known_provider(self, client: TestClient) -> None:
        mock_reg = _make_mock_registry(["groq"])
        with patch("app.api.v1.endpoints.providers.get_registry", return_value=mock_reg):
            resp = client.get("/api/v1/providers/groq")
        assert resp.status_code == 200

    def test_returns_provider_name(self, client: TestClient) -> None:
        mock_reg = _make_mock_registry(["groq"])
        with patch("app.api.v1.endpoints.providers.get_registry", return_value=mock_reg):
            resp = client.get("/api/v1/providers/groq")
        assert resp.json()["name"] == "groq"

    def test_returns_capabilities(self, client: TestClient) -> None:
        mock_reg = _make_mock_registry(["groq"])
        with patch("app.api.v1.endpoints.providers.get_registry", return_value=mock_reg):
            resp = client.get("/api/v1/providers/groq")
        assert "capabilities" in resp.json()
        assert "chat" in resp.json()["capabilities"]

    def test_returns_404_for_unknown_provider(self, client: TestClient) -> None:
        empty_reg = ProviderRegistry()
        with patch("app.api.v1.endpoints.providers.get_registry", return_value=empty_reg):
            resp = client.get("/api/v1/providers/nonexistent")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "INVALID_PROVIDER"


# ── GET /api/v1/providers/{provider}/models ───────────────────────────────────


class TestProviderModelsEndpoint:
    def test_returns_200_for_known_provider(self, client: TestClient) -> None:
        mock_reg = _make_mock_registry(["groq"])
        with patch("app.api.v1.endpoints.providers.get_registry", return_value=mock_reg):
            resp = client.get("/api/v1/providers/groq/models")
        assert resp.status_code == 200

    def test_returns_models_list(self, client: TestClient) -> None:
        mock_reg = _make_mock_registry(["groq"])
        with patch("app.api.v1.endpoints.providers.get_registry", return_value=mock_reg):
            resp = client.get("/api/v1/providers/groq/models")
        data = resp.json()
        assert "models" in data
        assert isinstance(data["models"], list)
        assert len(data["models"]) > 0

    def test_returns_provider_name_in_response(self, client: TestClient) -> None:
        mock_reg = _make_mock_registry(["groq"])
        with patch("app.api.v1.endpoints.providers.get_registry", return_value=mock_reg):
            resp = client.get("/api/v1/providers/groq/models")
        assert resp.json()["provider"] == "groq"

    def test_returns_404_for_unknown_provider(self, client: TestClient) -> None:
        empty_reg = ProviderRegistry()
        with patch("app.api.v1.endpoints.providers.get_registry", return_value=empty_reg):
            resp = client.get("/api/v1/providers/badprovider/models")
        assert resp.status_code == 404
