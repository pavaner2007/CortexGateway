"""
Cortex Gateway — Phase 2 Provider Unit Tests.

Tests:
- ProviderRegistry: register, retrieve, unknown provider.
- Response normalization for each provider (mocked).
- Validation: empty messages, invalid role, bad temperature, bad max_tokens.
- Error mapping: invalid provider, timeout, rate limit, auth, unavailable.
- Response metadata: provider name, model, request_id, latency, usage.

No real API credentials required — all external calls are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChatMessageResponse,
    ResponseMetadata,
    UsageMetadata,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_request(
    provider: str = "groq",
    model: str = "llama-3.3-70b-versatile",
    content: str = "Hello",
) -> ChatCompletionRequest:
    return ChatCompletionRequest(
        provider=provider,
        model=model,
        messages=[ChatMessage(role="user", content=content)],
        temperature=0.7,
        max_tokens=100,
    )


def _make_response(provider: str = "groq", model: str = "llama-3.3-70b-versatile") -> ChatCompletionResponse:
    return ChatCompletionResponse(
        provider=provider,
        model=model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessageResponse(content="Test response"),
                finish_reason="stop",
            )
        ],
        usage=UsageMetadata(prompt_tokens=10, completion_tokens=15, total_tokens=25),
        metadata=ResponseMetadata(request_id="test-req-id", latency_ms=123.4),
    )


# ── Registry Tests ────────────────────────────────────────────────────────────


class TestProviderRegistry:
    def test_register_and_retrieve(self) -> None:
        """Registered provider is retrievable by name."""
        reg = ProviderRegistry()
        mock_provider = MagicMock()
        mock_provider.name = "testprovider"
        reg.register(mock_provider)
        assert reg.get("testprovider") is mock_provider

    def test_retrieve_case_insensitive(self) -> None:
        """Provider lookup is case-insensitive."""
        reg = ProviderRegistry()
        mock_provider = MagicMock()
        mock_provider.name = "groq"
        reg.register(mock_provider)
        assert reg.get("GROQ") is mock_provider
        assert reg.get("Groq") is mock_provider

    def test_unknown_provider_raises(self) -> None:
        """Retrieving an unregistered provider raises InvalidProviderError."""
        reg = ProviderRegistry()
        with pytest.raises(InvalidProviderError) as exc_info:
            reg.get("unknown")
        assert "unknown" in exc_info.value.message.lower()
        assert exc_info.value.code == "INVALID_PROVIDER"

    def test_is_registered(self) -> None:
        """is_registered returns correct booleans."""
        reg = ProviderRegistry()
        mock_provider = MagicMock()
        mock_provider.name = "openai"
        reg.register(mock_provider)
        assert reg.is_registered("openai") is True
        assert reg.is_registered("gemini") is False

    def test_list_providers(self) -> None:
        """list_providers returns safe metadata without secrets."""
        reg = ProviderRegistry()
        for name in ["groq", "openai"]:
            mp = MagicMock()
            mp.name = name
            reg.register(mp)
        providers = reg.list_providers()
        names = {p.name for p in providers}
        assert names == {"groq", "openai"}
        # Verify no secrets are in provider info
        for p in providers:
            assert not hasattr(p, "api_key")

    def test_provider_names_sorted(self) -> None:
        """provider_names returns sorted list."""
        reg = ProviderRegistry()
        for name in ["openai", "groq", "gemini"]:
            mp = MagicMock()
            mp.name = name
            reg.register(mp)
        assert reg.provider_names == ["gemini", "groq", "openai"]


# ── Schema Validation Tests ───────────────────────────────────────────────────


class TestChatRequestValidation:
    def test_valid_request(self) -> None:
        """Valid request is accepted."""
        req = _make_request()
        assert req.provider == "groq"
        assert req.model == "llama-3.3-70b-versatile"

    def test_provider_normalized_to_lowercase(self) -> None:
        """Provider name is normalized to lowercase."""
        req = ChatCompletionRequest(
            provider="GROQ",
            model="llama-3.3-70b-versatile",
            messages=[ChatMessage(role="user", content="Hi")],
        )
        assert req.provider == "groq"

    def test_empty_messages_rejected(self) -> None:
        """Empty messages list raises ValidationError."""
        with pytest.raises(Exception):
            ChatCompletionRequest(
                provider="groq",
                model="llama-3.3-70b-versatile",
                messages=[],
            )

    def test_empty_content_rejected(self) -> None:
        """Empty message content raises ValidationError."""
        with pytest.raises(Exception):
            ChatMessage(role="user", content="")

    def test_whitespace_only_content_rejected(self) -> None:
        """Whitespace-only content raises ValidationError."""
        with pytest.raises(Exception):
            ChatMessage(role="user", content="   ")

    def test_invalid_role_rejected(self) -> None:
        """Invalid role raises ValidationError."""
        with pytest.raises(Exception):
            ChatMessage(role="robot", content="Hello")  # type: ignore

    def test_temperature_too_high_rejected(self) -> None:
        """Temperature > 2.0 is rejected."""
        with pytest.raises(Exception):
            ChatCompletionRequest(
                provider="groq",
                model="test-model",
                messages=[ChatMessage(role="user", content="Hi")],
                temperature=3.0,
            )

    def test_temperature_negative_rejected(self) -> None:
        """Negative temperature is rejected."""
        with pytest.raises(Exception):
            ChatCompletionRequest(
                provider="groq",
                model="test-model",
                messages=[ChatMessage(role="user", content="Hi")],
                temperature=-0.1,
            )

    def test_max_tokens_zero_rejected(self) -> None:
        """max_tokens=0 is rejected (must be > 0)."""
        with pytest.raises(Exception):
            ChatCompletionRequest(
                provider="groq",
                model="test-model",
                messages=[ChatMessage(role="user", content="Hi")],
                max_tokens=0,
            )

    def test_max_tokens_negative_rejected(self) -> None:
        """Negative max_tokens is rejected."""
        with pytest.raises(Exception):
            ChatCompletionRequest(
                provider="groq",
                model="test-model",
                messages=[ChatMessage(role="user", content="Hi")],
                max_tokens=-100,
            )

    def test_top_p_out_of_range_rejected(self) -> None:
        """top_p > 1.0 is rejected."""
        with pytest.raises(Exception):
            ChatCompletionRequest(
                provider="groq",
                model="test-model",
                messages=[ChatMessage(role="user", content="Hi")],
                top_p=1.5,
            )

    def test_all_valid_roles_accepted(self) -> None:
        """All three valid roles are accepted."""
        for role in ("system", "user", "assistant"):
            msg = ChatMessage(role=role, content="Test")  # type: ignore
            assert msg.role == role

    def test_optional_params_can_be_omitted(self) -> None:
        """Optional parameters have None defaults."""
        req = ChatCompletionRequest(
            provider="groq",
            model="test-model",
            messages=[ChatMessage(role="user", content="Hi")],
        )
        assert req.temperature is None
        assert req.max_tokens is None
        assert req.top_p is None
        assert req.stop is None


# ── Provider Adapter Mock Tests ───────────────────────────────────────────────


class TestGroqProviderNormalization:
    """Test Groq response normalization (all external calls mocked)."""

    @pytest.mark.asyncio
    async def test_chat_returns_normalized_response(self) -> None:
        """Groq chat returns Cortex ChatCompletionResponse."""
        with patch("app.providers.groq_provider.AsyncGroq") as MockGroq:
            mock_client = MagicMock()
            MockGroq.return_value = mock_client

            # Build mock completion
            mock_choice = MagicMock()
            mock_choice.index = 0
            mock_choice.message.content = "Docker is a containerization tool."
            mock_choice.finish_reason = "stop"

            mock_usage = MagicMock()
            mock_usage.prompt_tokens = 12
            mock_usage.completion_tokens = 8
            mock_usage.total_tokens = 20

            mock_completion = MagicMock()
            mock_completion.model = "llama-3.3-70b-versatile"
            mock_completion.choices = [mock_choice]
            mock_completion.usage = mock_usage

            mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

            from app.providers.groq_provider import GroqProvider
            provider = GroqProvider(api_key="test-key")
            req = _make_request(provider="groq")
            response = await provider.chat(req, "req-123")

        assert isinstance(response, ChatCompletionResponse)
        assert response.provider == "groq"
        assert response.choices[0].message.content == "Docker is a containerization tool."
        assert response.usage.prompt_tokens == 12
        assert response.usage.completion_tokens == 8
        assert response.usage.total_tokens == 20
        assert response.metadata.request_id == "req-123"
        assert response.metadata.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_groq_timeout_raises_provider_timeout(self) -> None:
        """Groq APITimeoutError is translated to ProviderTimeoutError."""
        from groq import APITimeoutError

        with patch("app.providers.groq_provider.AsyncGroq") as MockGroq:
            mock_client = MagicMock()
            MockGroq.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(
                side_effect=APITimeoutError(request=MagicMock())
            )

            from app.providers.groq_provider import GroqProvider
            provider = GroqProvider(api_key="test-key")
            with pytest.raises(ProviderTimeoutError) as exc_info:
                await provider.chat(_make_request(), "req-456")

        assert exc_info.value.code == "PROVIDER_TIMEOUT"
        assert exc_info.value.status_code == 504

    @pytest.mark.asyncio
    async def test_groq_rate_limit_raises_provider_rate_limit(self) -> None:
        """Groq 429 is translated to ProviderRateLimitError."""
        from groq import APIStatusError

        with patch("app.providers.groq_provider.AsyncGroq") as MockGroq:
            mock_client = MagicMock()
            MockGroq.return_value = mock_client
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_client.chat.completions.create = AsyncMock(
                side_effect=APIStatusError(
                    "Rate limited", response=mock_response, body={}
                )
            )

            from app.providers.groq_provider import GroqProvider
            provider = GroqProvider(api_key="test-key")
            with pytest.raises(ProviderRateLimitError) as exc_info:
                await provider.chat(_make_request(), "req-789")

        assert exc_info.value.code == "PROVIDER_RATE_LIMITED"
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_groq_auth_error_raises_provider_auth_error(self) -> None:
        """Groq 401 is translated to ProviderAuthError."""
        from groq import APIStatusError

        with patch("app.providers.groq_provider.AsyncGroq") as MockGroq:
            mock_client = MagicMock()
            MockGroq.return_value = mock_client
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_client.chat.completions.create = AsyncMock(
                side_effect=APIStatusError(
                    "Unauthorized", response=mock_response, body={}
                )
            )

            from app.providers.groq_provider import GroqProvider
            provider = GroqProvider(api_key="bad-key")
            with pytest.raises(ProviderAuthError) as exc_info:
                await provider.chat(_make_request(), "req-auth")

        assert exc_info.value.code == "PROVIDER_AUTHENTICATION_FAILED"
        assert exc_info.value.status_code == 502


class TestOpenAIProviderNormalization:
    """Test OpenAI response normalization (all external calls mocked)."""

    @pytest.mark.asyncio
    async def test_chat_returns_normalized_response(self) -> None:
        """OpenAI chat returns Cortex ChatCompletionResponse."""
        with patch("app.providers.openai_provider.AsyncOpenAI") as MockOAI:
            mock_client = MagicMock()
            MockOAI.return_value = mock_client

            mock_choice = MagicMock()
            mock_choice.index = 0
            mock_choice.message.content = "OpenAI response"
            mock_choice.finish_reason = "stop"

            mock_usage = MagicMock()
            mock_usage.prompt_tokens = 5
            mock_usage.completion_tokens = 10
            mock_usage.total_tokens = 15

            mock_completion = MagicMock()
            mock_completion.model = "gpt-4o-mini"
            mock_completion.choices = [mock_choice]
            mock_completion.usage = mock_usage

            mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

            from app.providers.openai_provider import OpenAIProvider
            provider = OpenAIProvider(api_key="test-key")
            req = _make_request(provider="openai", model="gpt-4o-mini")
            response = await provider.chat(req, "openai-req-1")

        assert response.provider == "openai"
        assert response.choices[0].message.content == "OpenAI response"
        assert response.usage.total_tokens == 15
        assert response.metadata.request_id == "openai-req-1"

    @pytest.mark.asyncio
    async def test_openai_timeout_raises_provider_timeout(self) -> None:
        """OpenAI APITimeoutError → ProviderTimeoutError."""
        from openai import APITimeoutError

        with patch("app.providers.openai_provider.AsyncOpenAI") as MockOAI:
            mock_client = MagicMock()
            MockOAI.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(
                side_effect=APITimeoutError(request=MagicMock())
            )

            from app.providers.openai_provider import OpenAIProvider
            provider = OpenAIProvider(api_key="test-key")
            with pytest.raises(ProviderTimeoutError):
                await provider.chat(_make_request(provider="openai", model="gpt-4o-mini"), "t1")

    @pytest.mark.asyncio
    async def test_openai_auth_error_raises_provider_auth_error(self) -> None:
        """OpenAI 401 → ProviderAuthError."""
        from openai import APIStatusError

        with patch("app.providers.openai_provider.AsyncOpenAI") as MockOAI:
            mock_client = MagicMock()
            MockOAI.return_value = mock_client
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.headers = {}
            mock_client.chat.completions.create = AsyncMock(
                side_effect=APIStatusError(
                    "Unauthorized", response=mock_response, body={}
                )
            )

            from app.providers.openai_provider import OpenAIProvider
            provider = OpenAIProvider(api_key="bad-key")
            with pytest.raises(ProviderAuthError):
                await provider.chat(
                    _make_request(provider="openai", model="gpt-4o-mini"), "t2"
                )


class TestGeminiProviderNormalization:
    """Test Gemini response normalization (all external calls mocked)."""

    @pytest.mark.asyncio
    async def test_chat_returns_normalized_response(self) -> None:
        """Gemini chat returns Cortex ChatCompletionResponse."""
        with (
            patch("app.providers.gemini_provider.genai.configure"),
            patch("app.providers.gemini_provider.genai.GenerativeModel") as MockModel,
        ):
            mock_model_instance = MagicMock()
            MockModel.return_value = mock_model_instance

            mock_chat = MagicMock()
            mock_model_instance.start_chat.return_value = mock_chat

            mock_response = MagicMock()
            mock_response.text = "Gemini response text"
            mock_response.candidates = [MagicMock()]
            mock_response.candidates[0].finish_reason.name = "STOP"

            mock_usage = MagicMock()
            mock_usage.prompt_token_count = 8
            mock_usage.candidates_token_count = 12
            mock_usage.total_token_count = 20
            mock_response.usage_metadata = mock_usage

            mock_chat.send_message_async = AsyncMock(return_value=mock_response)

            from app.providers.gemini_provider import GeminiProvider
            provider = GeminiProvider(api_key="test-key")
            req = _make_request(provider="gemini", model="gemini-1.5-flash")
            response = await provider.chat(req, "gem-req-1")

        assert response.provider == "gemini"
        assert response.choices[0].message.content == "Gemini response text"
        assert response.usage.prompt_tokens == 8
        assert response.usage.completion_tokens == 12
        assert response.usage.total_tokens == 20
        assert response.metadata.request_id == "gem-req-1"


# ── Response Metadata Tests ───────────────────────────────────────────────────


class TestResponseMetadata:
    def test_response_has_required_fields(self) -> None:
        """ChatCompletionResponse contains all required metadata fields."""
        response = _make_response()
        assert response.provider == "groq"
        assert response.model == "llama-3.3-70b-versatile"
        assert response.metadata.request_id == "test-req-id"
        assert response.metadata.latency_ms == 123.4
        assert response.usage.total_tokens == 25

    def test_response_id_has_ctx_prefix(self) -> None:
        """Auto-generated response ID has 'ctx_' prefix."""
        response = _make_response()
        assert response.id.startswith("ctx_")

    def test_response_object_type(self) -> None:
        """Response object type is 'chat.completion'."""
        response = _make_response()
        assert response.object == "chat.completion"

    def test_usage_can_be_none(self) -> None:
        """Usage fields can be None when provider doesn't return them."""
        usage = UsageMetadata()
        assert usage.prompt_tokens is None
        assert usage.completion_tokens is None
        assert usage.total_tokens is None
