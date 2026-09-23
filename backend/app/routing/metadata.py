"""
Cortex Gateway — Model Metadata Catalog (Phase 3 + Phase 9A).

Phase 9A: ModelMetadataCatalog is now backed by the PostgreSQL model_registry
table instead of the static _DEFAULT_CATALOG dict.

The catalog is populated at startup and refreshed every 60 seconds by a
background task registered in main.py. Between refresh cycles the in-memory
dict is served synchronously — same interface as before, zero per-request
DB overhead.

Fallback behavior (unchanged from Phase 3):
  - If a model is not in the catalog (e.g. an unlisted Ollama model),
    a safe, deterministic default is returned.
  - This fallback is intentional: dynamic Ollama models that haven't been
    registered yet still get a usable ModelMetadata.

Module-level singleton:
  _shared_catalog  — single ModelMetadataCatalog instance used by both
                     routing engine (Phase 3) and cost calculator (Phase 6).
"""

from __future__ import annotations

import asyncio

from app.routing.models import ModelMetadata


class ModelMetadataCatalog:
    """
    Catalog service resolving model metadata with configurable fallbacks.

    Backed by the model_registry PostgreSQL table (Phase 9A).
    The in-memory dict is loaded/refreshed via load_from_db().
    The get() method is synchronous for Phase 3 / Phase 6 compatibility.
    """

    def __init__(
        self,
        ollama_default_cost: float = 0.0,
    ) -> None:
        self._catalog: dict[str, ModelMetadata] = {}
        self._ollama_default_cost = ollama_default_cost
        self._lock = asyncio.Lock()

    async def load_from_db(self, session) -> None:
        """
        (Re)populate the in-memory catalog from the model_registry table.

        Called:
          - Once at application startup.
          - Periodically (every 60 s) by the background refresh task.
          - Immediately after any admin mutation via the model registry API.

        The lock ensures concurrent refreshes do not corrupt the dict.
        """
        from app.model_registry.service import ModelRegistryService

        service = ModelRegistryService(session=session)
        entries = await service.get_all_for_catalog()

        new_catalog: dict[str, ModelMetadata] = {}
        for entry in entries:
            key = f"{entry.provider}:{entry.model_name}"
            new_catalog[key] = ModelMetadata(
                provider=entry.provider,
                model=entry.model_name,
                cost_per_1k_tokens=entry.cost_per_1k_tokens,
                input_cost_per_1k=entry.input_cost_per_1k,
                output_cost_per_1k=entry.output_cost_per_1k,
                capabilities=list(entry.capabilities),
                context_window=entry.context_window,
                baseline_latency_ms=entry.baseline_latency_ms,
            )

        async with self._lock:
            self._catalog = new_catalog

        from app.core.logging import logger
        logger.debug(
            "ModelMetadataCatalog refreshed from DB",
            total=len(new_catalog),
        )

    def get(self, provider: str, model: str) -> ModelMetadata:
        """
        Retrieve metadata for a provider + model.

        If the model is not in the catalog (e.g. a newly pulled Ollama model
        not yet registered), returns a safe, deterministic default.

        This method is synchronous for Phase 3 / Phase 6 compatibility.
        """
        key = f"{provider.lower()}:{model.strip()}"
        if key in self._catalog:
            return self._catalog[key]

        # Check by bare model name without tag (e.g. 'llama3.2:3b' → 'llama3.2')
        bare_model = model.split(":")[0].strip()
        bare_key = f"{provider.lower()}:{bare_model}"
        if bare_key in self._catalog:
            entry = self._catalog[bare_key]
            return ModelMetadata(
                provider=provider,
                model=model,
                cost_per_1k_tokens=entry.cost_per_1k_tokens,
                input_cost_per_1k=entry.input_cost_per_1k,
                output_cost_per_1k=entry.output_cost_per_1k,
                capabilities=entry.capabilities,
                context_window=entry.context_window,
                baseline_latency_ms=entry.baseline_latency_ms,
            )

        # Default fallback for uncatalogued models
        is_ollama = provider.lower() == "ollama"
        cost = self._ollama_default_cost if is_ollama else 0.0005
        baseline_lat = 300.0 if is_ollama else 500.0
        caps: list[str] = ["text", "code", "json"]

        if "vision" in model.lower() or "llava" in model.lower():
            caps.append("vision")

        return ModelMetadata(
            provider=provider.lower(),
            model=model,
            cost_per_1k_tokens=cost,
            capabilities=caps,
            context_window=8192,
            baseline_latency_ms=baseline_lat,
        )

    def provider_model_names(self, provider: str) -> list[str]:
        """
        Return model names registered for a specific provider.
        Used by CandidateBuilder as fallback when provider.list_models() is empty.
        """
        prefix = f"{provider.lower()}:"
        return [
            meta.model
            for key, meta in self._catalog.items()
            if key.startswith(prefix)
        ]

    @property
    def size(self) -> int:
        """Number of models currently in the in-memory catalog."""
        return len(self._catalog)


# ── Module-level singleton ────────────────────────────────────────────────────
# Shared by RoutingEngine (Phase 3) and CostCalculator (Phase 6).
# Loaded on startup; refreshed every 60 s by background task in main.py.
_shared_catalog = ModelMetadataCatalog()
