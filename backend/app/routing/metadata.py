"""
Cortex Gateway — Model Metadata Catalog (Phase 3).

Configuration-driven metadata catalog specifying costs, capabilities,
context windows, and baseline latencies for supported models across providers.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from app.routing.models import ModelMetadata

# Model catalog mapping (provider, normalized_model) -> ModelMetadata
_DEFAULT_CATALOG: Dict[str, ModelMetadata] = {
    # ── Google Gemini (Cloud) ─────────────────────────────────────────────────
    "gemini:gemini-1.5-flash": ModelMetadata(
        provider="gemini",
        model="gemini-1.5-flash",
        cost_per_1k_tokens=0.00015,
        capabilities=["text", "vision", "json", "code"],
        context_window=1000000,
        baseline_latency_ms=450.0,
    ),
    "gemini:gemini-1.5-pro": ModelMetadata(
        provider="gemini",
        model="gemini-1.5-pro",
        cost_per_1k_tokens=0.0025,
        capabilities=["text", "vision", "json", "code", "complex_reasoning"],
        context_window=2000000,
        baseline_latency_ms=900.0,
    ),
    "gemini:gemini-2.0-flash": ModelMetadata(
        provider="gemini",
        model="gemini-2.0-flash",
        cost_per_1k_tokens=0.00010,
        capabilities=["text", "vision", "json", "code", "tools"],
        context_window=1000000,
        baseline_latency_ms=350.0,
    ),
    "gemini:gemini-2.5-flash": ModelMetadata(
        provider="gemini",
        model="gemini-2.5-flash",
        cost_per_1k_tokens=0.00010,
        capabilities=["text", "vision", "json", "code", "tools"],
        context_window=1000000,
        baseline_latency_ms=350.0,
    ),
    # ── Groq (Cloud / Ultra-low latency) ──────────────────────────────────────
    "groq:llama-3.3-70b-versatile": ModelMetadata(
        provider="groq",
        model="llama-3.3-70b-versatile",
        cost_per_1k_tokens=0.00059,
        capabilities=["text", "json", "code", "tools"],
        context_window=128000,
        baseline_latency_ms=180.0,
    ),
    "groq:llama-3.1-8b-instant": ModelMetadata(
        provider="groq",
        model="llama-3.1-8b-instant",
        cost_per_1k_tokens=0.00005,
        capabilities=["text", "json", "code"],
        context_window=128000,
        baseline_latency_ms=90.0,
    ),
    "groq:llama3-8b-8192": ModelMetadata(
        provider="groq",
        model="llama3-8b-8192",
        cost_per_1k_tokens=0.00005,
        capabilities=["text", "json", "code"],
        context_window=8192,
        baseline_latency_ms=100.0,
    ),
    "groq:llama3-70b-8192": ModelMetadata(
        provider="groq",
        model="llama3-70b-8192",
        cost_per_1k_tokens=0.00059,
        capabilities=["text", "json", "code", "tools"],
        context_window=8192,
        baseline_latency_ms=220.0,
    ),
    "groq:mixtral-8x7b-32768": ModelMetadata(
        provider="groq",
        model="mixtral-8x7b-32768",
        cost_per_1k_tokens=0.00024,
        capabilities=["text", "json", "code"],
        context_window=32768,
        baseline_latency_ms=150.0,
    ),
    "groq:gemma2-9b-it": ModelMetadata(
        provider="groq",
        model="gemma2-9b-it",
        cost_per_1k_tokens=0.00010,
        capabilities=["text", "code"],
        context_window=8192,
        baseline_latency_ms=130.0,
    ),
    # ── Ollama (Local / Self-hosted) ──────────────────────────────────────────
    "ollama:llama3.2": ModelMetadata(
        provider="ollama",
        model="llama3.2",
        cost_per_1k_tokens=0.00,
        capabilities=["text", "json", "code"],
        context_window=8192,
        baseline_latency_ms=300.0,
    ),
    "ollama:llama3.2:latest": ModelMetadata(
        provider="ollama",
        model="llama3.2:latest",
        cost_per_1k_tokens=0.00,
        capabilities=["text", "json", "code"],
        context_window=8192,
        baseline_latency_ms=300.0,
    ),
    "ollama:llama3.2-vision": ModelMetadata(
        provider="ollama",
        model="llama3.2-vision",
        cost_per_1k_tokens=0.00,
        capabilities=["text", "vision", "code"],
        context_window=8192,
        baseline_latency_ms=450.0,
    ),
    "ollama:qwen2.5": ModelMetadata(
        provider="ollama",
        model="qwen2.5",
        cost_per_1k_tokens=0.00,
        capabilities=["text", "json", "code"],
        context_window=32768,
        baseline_latency_ms=280.0,
    ),
    "ollama:qwen2.5:latest": ModelMetadata(
        provider="ollama",
        model="qwen2.5:latest",
        cost_per_1k_tokens=0.00,
        capabilities=["text", "json", "code"],
        context_window=32768,
        baseline_latency_ms=280.0,
    ),
}


class ModelMetadataCatalog:
    """Catalog service resolving model metadata with configurable fallbacks."""

    def __init__(
        self,
        custom_metadata: Optional[Dict[str, ModelMetadata]] = None,
        ollama_default_cost: float = 0.0,
    ) -> None:
        self._catalog: Dict[str, ModelMetadata] = dict(_DEFAULT_CATALOG)
        if custom_metadata:
            self._catalog.update(custom_metadata)
        self._ollama_default_cost = ollama_default_cost

    def get(self, provider: str, model: str) -> ModelMetadata:
        """
        Retrieve metadata for a provider + model.

        If the model is not explicitly cataloged (e.g. newly pulled Ollama model),
        returns a safe, deterministic default.
        """
        key = f"{provider.lower()}:{model.strip()}"
        if key in self._catalog:
            return self._catalog[key]

        # Check by bare model name without tag (e.g. 'llama3.2:3b' -> 'llama3.2')
        bare_model = model.split(":")[0].strip()
        bare_key = f"{provider.lower()}:{bare_model}"
        if bare_key in self._catalog:
            entry = self._catalog[bare_key]
            return ModelMetadata(
                provider=provider,
                model=model,
                cost_per_1k_tokens=entry.cost_per_1k_tokens,
                capabilities=entry.capabilities,
                context_window=entry.context_window,
                baseline_latency_ms=entry.baseline_latency_ms,
            )

        # Default fallback
        is_ollama = provider.lower() == "ollama"
        cost = self._ollama_default_cost if is_ollama else 0.0005
        baseline_lat = 300.0 if is_ollama else 500.0
        caps = ["text", "code", "json"]

        # If model name hints at vision (e.g. llava, vision)
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
