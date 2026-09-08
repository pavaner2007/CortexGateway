"""
Cortex Gateway — Provider Discovery Endpoints (Phase 2).

Provides:
    GET /api/v1/providers                    — List all registered providers.
    GET /api/v1/providers/{provider}         — Provider details.
    GET /api/v1/providers/{provider}/models  — Available models for a provider.

API keys and secrets are NEVER returned.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.providers.exceptions import InvalidProviderError
from app.providers.registry import ProviderRegistry, get_registry
from app.schemas.chat import (
    ModelListResponse,
    ProviderDetailResponse,
    ProviderListResponse,
)

router = APIRouter()


@router.get(
    "/providers",
    response_model=ProviderListResponse,
    summary="List Providers",
    description="Returns all registered LLM providers and their availability status.",
    tags=["Providers"],
)
async def list_providers(
    reg: ProviderRegistry = Depends(get_registry),
) -> ProviderListResponse:
    """Return all registered providers with safe metadata."""
    return ProviderListResponse(providers=reg.list_providers())


@router.get(
    "/providers/{provider}",
    response_model=ProviderDetailResponse,
    summary="Provider Details",
    description="Returns detailed metadata for a specific provider.",
    tags=["Providers"],
    responses={
        404: {"description": "Provider not found"},
    },
)
async def get_provider(
    provider: str,
    reg: ProviderRegistry = Depends(get_registry),
) -> ProviderDetailResponse:
    """Return details for a specific registered provider."""
    p = reg.get(provider)  # raises InvalidProviderError → 404 via exception handler
    return ProviderDetailResponse(
        name=p.name,
        enabled=True,
        available=True,
        capabilities=["chat"],
    )


@router.get(
    "/providers/{provider}/models",
    response_model=ModelListResponse,
    summary="List Provider Models",
    description="Returns the list of available models for the specified provider.",
    tags=["Providers"],
    responses={
        404: {"description": "Provider not found"},
        503: {"description": "Provider unavailable"},
    },
)
async def list_provider_models(
    provider: str,
    reg: ProviderRegistry = Depends(get_registry),
) -> ModelListResponse:
    """Fetch and return available models for the specified provider."""
    p = reg.get(provider)  # raises InvalidProviderError → 404 via exception handler
    models = await p.list_models()
    return ModelListResponse(provider=p.name, models=models)
