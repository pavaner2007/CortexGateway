"""
Cortex Gateway — Routing Policies (Phase 3).

Defines scoring weight configurations for all supported routing modes:
- manual
- auto
- lowest_cost
- lowest_latency
- best_available
- capability_based
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
from app.routing.models import RoutingMode


@dataclass(frozen=True)
class PolicyWeights:
    health_weight: float
    success_rate_weight: float
    latency_weight: float
    cost_weight: float


# Default policy weight profiles
_POLICY_WEIGHTS: Dict[RoutingMode, PolicyWeights] = {
    # Auto: Balanced weights across all operational factors
    "auto": PolicyWeights(
        health_weight=0.30,
        success_rate_weight=0.30,
        latency_weight=0.20,
        cost_weight=0.20,
    ),
    # Lowest Cost: Prioritizes cost (60%) while maintaining baseline reliability
    "lowest_cost": PolicyWeights(
        health_weight=0.15,
        success_rate_weight=0.15,
        latency_weight=0.10,
        cost_weight=0.60,
    ),
    # Lowest Latency: Prioritizes response speed (60%)
    "lowest_latency": PolicyWeights(
        health_weight=0.15,
        success_rate_weight=0.15,
        latency_weight=0.60,
        cost_weight=0.10,
    ),
    # Best Available: Prioritizes health and success rate (80% combined)
    "best_available": PolicyWeights(
        health_weight=0.40,
        success_rate_weight=0.40,
        latency_weight=0.10,
        cost_weight=0.10,
    ),
    # Capability Based: Balanced scoring after strict capability pre-filtering
    "capability_based": PolicyWeights(
        health_weight=0.30,
        success_rate_weight=0.30,
        latency_weight=0.20,
        cost_weight=0.20,
    ),
    # Manual: Bypasses scoring
    "manual": PolicyWeights(
        health_weight=0.25,
        success_rate_weight=0.25,
        latency_weight=0.25,
        cost_weight=0.25,
    ),
}


class RoutingPolicyRegistry:
    """Provides policy weights for routing modes with configurable defaults."""

    def __init__(
        self,
        default_auto_weights: PolicyWeights | None = None,
    ) -> None:
        self._weights = dict(_POLICY_WEIGHTS)
        if default_auto_weights:
            self._weights["auto"] = default_auto_weights

    def get_weights(self, mode: RoutingMode) -> PolicyWeights:
        return self._weights.get(mode, self._weights["auto"])
