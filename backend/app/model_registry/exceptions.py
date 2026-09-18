"""
Cortex Gateway — Model Registry Exceptions (Phase 9A).
"""

from __future__ import annotations


class ModelRegistryError(Exception):
    """Base class for model registry errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ModelAlreadyExistsError(ModelRegistryError):
    """Raised when attempting to create a duplicate (provider, model_name) entry."""

    def __init__(self, provider: str, model_name: str) -> None:
        super().__init__(
            f"A registry entry already exists for provider={provider!r} "
            f"model={model_name!r}. Use PATCH to update it."
        )


class ModelNotFoundError(ModelRegistryError):
    """Raised when a requested model registry entry does not exist."""

    def __init__(self, model_id: str) -> None:
        super().__init__(f"Model registry entry {model_id!r} not found.")
