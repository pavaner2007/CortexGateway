"""
Cortex Gateway — Candidate Scorer (Phase 3).

Deterministic multi-factor weighted scoring engine.
Normalizes all factor scores to [0.0, 1.0]:
  - Health: 1.0 (healthy) or 0.0 (unhealthy)
  - Success Rate: [0.0, 1.0] from runtime stats / baseline
  - Latency: [0.0, 1.0] (lower latency = higher score)
  - Cost: [0.0, 1.0] (lower cost = higher score)

Provides deterministic tie-breaking so identical inputs always select the same candidate.
"""

from __future__ import annotations

from typing import Dict, List, NamedTuple, Tuple
from app.routing.models import RoutingCandidate


class ScoredCandidate(NamedTuple):
    candidate: RoutingCandidate
    total_score: float
    score_breakdown: Dict[str, float]


class CandidateScorer:
    """Computes normalized weighted scores for a set of routing candidates."""

    @staticmethod
    def _normalize_weights(
        health_w: float,
        success_w: float,
        latency_w: float,
        cost_w: float,
    ) -> Tuple[float, float, float, float]:
        """Normalize arbitrary positive weights so their sum equals 1.0."""
        total = health_w + success_w + latency_w + cost_w
        if total <= 0:
            return (0.25, 0.25, 0.25, 0.25)
        return (
            health_w / total,
            success_w / total,
            latency_w / total,
            cost_w / total,
        )

    def score_candidates(
        self,
        candidates: List[RoutingCandidate],
        health_weight: float = 0.30,
        success_rate_weight: Optional[float] = None,
        latency_weight: float = 0.20,
        cost_weight: float = 0.20,
        success_weight: Optional[float] = None,
        **kwargs: float,
    ) -> List[ScoredCandidate]:
        """
        Score and rank candidates deterministically in descending order.

        Returns:
            List of ScoredCandidate sorted from highest to lowest score.
        """
        if not candidates:
            return []

        # Support success_rate_weight or legacy success_weight alias
        eff_success_w = (
            success_rate_weight
            if success_rate_weight is not None
            else (success_weight if success_weight is not None else 0.30)
        )

        w_health, w_success, w_latency, w_cost = self._normalize_weights(
            health_weight, eff_success_w, latency_weight, cost_weight
        )

        # Collect latency and cost bounds across the candidate pool for normalization
        latencies = [c.effective_latency_ms for c in candidates]
        costs = [c.cost_per_1k_tokens for c in candidates]
        paid_costs = [cost for cost in costs if cost > 0.0]

        min_lat = min(latencies)
        max_lat = max(latencies)
        min_cost = min(costs)
        max_cost = max(costs)
        min_paid_cost = min(paid_costs) if paid_costs else 0.0

        scored: List[ScoredCandidate] = []

        for c in candidates:
            # 1. Health factor: 1.0 if healthy, else 0.0
            health_score = 1.0 if c.is_healthy else 0.0

            # 2. Success rate factor: directly in [0.0, 1.0]
            success_score = max(0.0, min(1.0, c.runtime_success_rate))

            # 3. Latency factor: lower latency -> higher score
            c_lat = c.effective_latency_ms
            if max_lat == min_lat:
                latency_score = 1.0
            else:
                # Ratio of min latency to candidate latency: min_lat / c_lat in (0, 1]
                latency_score = min_lat / c_lat if c_lat > 0 else 1.0

            # 4. Cost factor: lower cost -> higher score
            c_cost = c.cost_per_1k_tokens
            if max_cost == min_cost:
                cost_score = 1.0
            elif c_cost == 0.0:
                cost_score = 1.0
            elif min_cost == 0.0 and min_paid_cost > 0.0:
                # Free models exist; paid models receive scaled score capped below free tier
                cost_score = max(0.05, 0.75 * (min_paid_cost / c_cost))
            elif min_cost > 0.0:
                cost_score = min_cost / c_cost
            else:
                cost_score = 1.0

            # Calculate total weighted score
            total_score = (
                (health_score * w_health)
                + (success_score * w_success)
                + (latency_score * w_latency)
                + (cost_score * w_cost)
            )

            # Clamp to [0.0, 1.0]
            total_score = max(0.0, min(1.0, total_score))

            breakdown = {
                "health": round(health_score, 4),
                "success_rate": round(success_score, 4),
                "latency": round(latency_score, 4),
                "cost": round(cost_score, 4),
            }

            scored.append(
                ScoredCandidate(
                    candidate=c,
                    total_score=round(total_score, 4),
                    score_breakdown=breakdown,
                )
            )

        # Deterministic sorting:
        # 1. Highest total_score first (-total_score)
        # 2. Healthy candidates first (-is_healthy)
        # 3. Highest success rate first (-success_rate)
        # 4. Lowest latency first (effective_latency_ms)
        # 5. Lowest cost first (cost_per_1k_tokens)
        # 6. Alphabetical provider name
        # 7. Alphabetical model name
        scored.sort(
            key=lambda sc: (
                -sc.total_score,
                -int(sc.candidate.is_healthy),
                -sc.candidate.runtime_success_rate,
                sc.candidate.effective_latency_ms,
                sc.candidate.cost_per_1k_tokens,
                sc.candidate.provider,
                sc.candidate.model,
            )
        )

        return scored
