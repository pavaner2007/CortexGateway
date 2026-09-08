"""
Cortex Gateway — Providers Package.

Exports:
    BaseLLMProvider   — Abstract interface all providers implement.
    ProviderRegistry  — Central provider registry singleton.
    get_registry      — Accessor for the global registry instance.
    OpenAIProvider    — OpenAI adapter.
    GeminiProvider    — Google Gemini adapter.
    GroqProvider      — Groq adapter.
    ProviderException — Base provider exception.
    (all subclasses)  — Typed provider exceptions.
"""

from app.providers.base import BaseLLMProvider
from app.providers.exceptions import (
    InvalidModelError,
    InvalidProviderError,
    ProviderAuthError,
    ProviderDisabledError,
    ProviderError,
    ProviderException,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.providers.gemini_provider import GeminiProvider
from app.providers.groq_provider import GroqProvider
from app.providers.openai_provider import OpenAIProvider
from app.providers.registry import ProviderRegistry, get_registry, registry

__all__ = [
    "BaseLLMProvider",
    "ProviderRegistry",
    "get_registry",
    "registry",
    "OpenAIProvider",
    "GeminiProvider",
    "GroqProvider",
    "ProviderException",
    "InvalidProviderError",
    "ProviderDisabledError",
    "InvalidModelError",
    "ProviderTimeoutError",
    "ProviderRateLimitError",
    "ProviderUnavailableError",
    "ProviderAuthError",
    "ProviderError",
]
