"""
Cortex Gateway — Intelligent Routing Engine Package (Phase 3).

Exports:
    RoutingEngine          — Core routing orchestrator.
    RoutingMode            — Supported routing mode literal.
    RoutingCandidate       — Evaluation candidate model.
    RoutingDecision        — Result of a routing decision.
    ModelMetadata          — Model metadata structure.
    ModelMetadataCatalog   — Catalog service for model metadata.
    CandidateScorer        — Weighted scoring engine.
    ProviderStatsTracker   — Runtime in-memory statistics tracker.
    RoutingPolicyRegistry  — Policy weights registry.
    PolicyWeights          — Policy weight definitions.
    RoutingException       — Base routing exception.
    (typed exceptions)     — NoRoutableProviderError, NoCapableProviderError, etc.
"""

from app.routing.candidates import CandidateBuilder
from app.routing.exceptions import (
    InvalidManualRoutingError,
    InvalidRoutingModeError,
    NoCapableProviderError,
    NoRoutableProviderError,
    RoutingException,
)
from app.routing.metadata import ModelMetadataCatalog
from app.routing.models import (
    ModelMetadata,
    RoutingCandidate,
    RoutingDecision,
    RoutingMode,
)
from app.routing.policies import PolicyWeights, RoutingPolicyRegistry
from app.routing.router import RoutingEngine
from app.routing.scorer import CandidateScorer, ScoredCandidate
from app.routing.stats import ModelStats, ProviderStatsTracker

__all__ = [
    "RoutingEngine",
    "RoutingMode",
    "RoutingCandidate",
    "RoutingDecision",
    "ModelMetadata",
    "ModelMetadataCatalog",
    "CandidateBuilder",
    "CandidateScorer",
    "ScoredCandidate",
    "ProviderStatsTracker",
    "ModelStats",
    "RoutingPolicyRegistry",
    "PolicyWeights",
    "RoutingException",
    "NoRoutableProviderError",
    "NoCapableProviderError",
    "InvalidRoutingModeError",
    "InvalidManualRoutingError",
]
