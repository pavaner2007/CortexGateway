"""
Cortex Gateway — Provider Registry (Phase 2).

Central registry that maps provider names to BaseLLMProvider instances.
Initialized during application lifespan startup.

Design:
- Singleton instance (module-level) initialized once at startup.
- Thread-safe for reads (no mutation after startup).
- Provider lookup is O(1) dict access.
- Raises typed ProviderException subclasses — never raw KeyError.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from app.core.logging import logger
from app.providers.base import BaseLLMProvider
from app.providers.exceptions import InvalidProviderError, ProviderDisabledError
from app.schemas.chat import ProviderInfo


class ProviderRegistry:
    """
    Registry mapping provider names to their adapter instances.

    Usage:
        registry = ProviderRegistry()
        registry.register(OpenAIProvider(...))
        provider = registry.get("openai")
        response = await provider.chat(request, request_id)
    """

    def __init__(self) -> None:
        self._providers: Dict[str, BaseLLMProvider] = {}

    def register(self, provider: BaseLLMProvider) -> None:
        """
        Register a provider adapter under its canonical name.

        Args:
            provider: An initialized BaseLLMProvider implementation.
        """
        name = provider.name.lower()
        self._providers[name] = provider
        logger.info("Provider registered: {name}", name=name)

    def get(self, name: str) -> BaseLLMProvider:
        """
        Retrieve a provider by name.

        Args:
            name: Provider name (case-insensitive).

        Returns:
            The registered BaseLLMProvider instance.

        Raises:
            InvalidProviderError: Provider is not registered.
        """
        key = name.strip().lower()
        provider = self._providers.get(key)
        if provider is None:
            available = list(self._providers.keys())
            raise InvalidProviderError(
                f"Provider '{key}' is not available. "
                f"Available providers: {available or ['none']}."
            )
        return provider

    def is_registered(self, name: str) -> bool:
        """Return True if the provider is registered."""
        return name.strip().lower() in self._providers

    def list_providers(self) -> List[ProviderInfo]:
        """
        Return safe metadata for all registered providers.

        Returns:
            List of ProviderInfo (name, enabled, available).
            API keys are NEVER included.
        """
        return [
            ProviderInfo(name=name, enabled=True, available=True)
            for name in sorted(self._providers.keys())
        ]

    @property
    def provider_names(self) -> List[str]:
        """Return sorted list of registered provider names."""
        return sorted(self._providers.keys())


# ── Module-level singleton ────────────────────────────────────────────────────
# Initialized empty; populated during FastAPI lifespan startup.
registry: ProviderRegistry = ProviderRegistry()


def get_registry() -> ProviderRegistry:
    """Return the global provider registry (FastAPI dependency-injectable)."""
    return registry
