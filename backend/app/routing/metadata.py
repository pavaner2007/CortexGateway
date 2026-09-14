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
    # Pricing source: cloud.google.com/vertex-ai/generative-ai/pricing
    "gemini:gemini-1.5-flash": ModelMetadata(
        provider="gemini",
        model="gemini-1.5-flash",
        cost_per_1k_tokens=0.00015,
        input_cost_per_1k=0.000075,
        output_cost_per_1k=0.00030,
        capabilities=["text", "vision", "json", "code"],
        context_window=1000000,
        baseline_latency_ms=450.0,
    ),
    "gemini:gemini-1.5-pro": ModelMetadata(
        provider="gemini",
        model="gemini-1.5-pro",
        cost_per_1k_tokens=0.0025,
        input_cost_per_1k=0.00125,
        output_cost_per_1k=0.00500,
        capabilities=["text", "vision", "json", "code", "complex_reasoning"],
        context_window=2000000,
        baseline_latency_ms=900.0,
    ),
    "gemini:gemini-2.0-flash": ModelMetadata(
        provider="gemini",
        model="gemini-2.0-flash",
        cost_per_1k_tokens=0.00010,
        input_cost_per_1k=0.000100,
        output_cost_per_1k=0.000400,
        capabilities=["text", "vision", "json", "code", "tools"],
        context_window=1000000,
        baseline_latency_ms=350.0,
    ),
    "gemini:gemini-2.5-flash": ModelMetadata(
        provider="gemini",
        model="gemini-2.5-flash",
        cost_per_1k_tokens=0.00010,
        input_cost_per_1k=0.000100,
        output_cost_per_1k=0.000400,
        capabilities=["text", "vision", "json", "code", "tools"],
        context_window=1000000,
        baseline_latency_ms=350.0,
    ),
    # ── Groq (Cloud / Ultra-low latency) ──────────────────────────────────────
    # Pricing source: console.groq.com/docs/openai
    "groq:llama-3.3-70b-versatile": ModelMetadata(
        provider="groq",
        model="llama-3.3-70b-versatile",
        cost_per_1k_tokens=0.00059,
        input_cost_per_1k=0.00059,
        output_cost_per_1k=0.00079,
        capabilities=["text", "json", "code", "tools"],
        context_window=128000,
        baseline_latency_ms=180.0,
    ),
    "groq:llama-3.1-8b-instant": ModelMetadata(
        provider="groq",
        model="llama-3.1-8b-instant",
        cost_per_1k_tokens=0.00005,
        input_cost_per_1k=0.00005,
        output_cost_per_1k=0.00008,
        capabilities=["text", "json", "code"],
        context_window=128000,
        baseline_latency_ms=90.0,
    ),
    "groq:llama3-8b-8192": ModelMetadata(
        provider="groq",
        model="llama3-8b-8192",
        cost_per_1k_tokens=0.00005,
        input_cost_per_1k=0.00005,
        output_cost_per_1k=0.00008,
        capabilities=["text", "json", "code"],
        context_window=8192,
        baseline_latency_ms=100.0,
    ),
    "groq:llama3-70b-8192": ModelMetadata(
        provider="groq",
        model="llama3-70b-8192",
        cost_per_1k_tokens=0.00059,
        input_cost_per_1k=0.00059,
        output_cost_per_1k=0.00079,
        capabilities=["text", "json", "code", "tools"],
        context_window=8192,
        baseline_latency_ms=220.0,
    ),
    "groq:mixtral-8x7b-32768": ModelMetadata(
        provider="groq",
        model="mixtral-8x7b-32768",
        cost_per_1k_tokens=0.00024,
        input_cost_per_1k=0.00024,
        output_cost_per_1k=0.00024,
        capabilities=["text", "json", "code"],
        context_window=32768,
        baseline_latency_ms=150.0,
    ),
    "groq:gemma2-9b-it": ModelMetadata(
        provider="groq",
        model="gemma2-9b-it",
        cost_per_1k_tokens=0.00010,
        input_cost_per_1k=0.00010,
        output_cost_per_1k=0.00010,
        capabilities=["text", "code"],
        context_window=8192,
        baseline_latency_ms=130.0,
    ),
    # ── Ollama (Local / Self-hosted) ──────────────────────────────────────────
    # Ollama has no per-token API charge by default.
    # Costs are configurable via OLLAMA_COST_PER_1K_INPUT/OUTPUT_TOKENS.
    "ollama:llama3.2": ModelMetadata(
        provider="ollama",
        model="llama3.2",
        cost_per_1k_tokens=0.00,
        input_cost_per_1k=0.00,
        output_cost_per_1k=0.00,
        capabilities=["text", "json", "code"],
        context_window=8192,
        baseline_latency_ms=300.0,
    ),
    "ollama:llama3.2:latest": ModelMetadata(
        provider="ollama",
        model="llama3.2:latest",
        cost_per_1k_tokens=0.00,
        input_cost_per_1k=0.00,
        output_cost_per_1k=0.00,
        capabilities=["text", "json", "code"],
        context_window=8192,
        baseline_latency_ms=300.0,
    ),
    "ollama:llama3.2-vision": ModelMetadata(
        provider="ollama",
        model="llama3.2-vision",
        cost_per_1k_tokens=0.00,
        input_cost_per_1k=0.00,
        output_cost_per_1k=0.00,
        capabilities=["text", "vision", "code"],
        context_window=8192,
        baseline_latency_ms=450.0,
    ),
    "ollama:qwen2.5": ModelMetadata(
        provider="ollama",
        model="qwen2.5",
        cost_per_1k_tokens=0.00,
        input_cost_per_1k=0.00,
        output_cost_per_1k=0.00,
        capabilities=["text", "json", "code"],
        context_window=32768,
        baseline_latency_ms=280.0,
    ),
    "ollama:qwen2.5:latest": ModelMetadata(
        provider="ollama",
        model="qwen2.5:latest",
        cost_per_1k_tokens=0.00,
        input_cost_per_1k=0.00,
        output_cost_per_1k=0.00,
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
                input_cost_per_1k=entry.input_cost_per_1k,
                output_cost_per_1k=entry.output_cost_per_1k,
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
