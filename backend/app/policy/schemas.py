"""
Cortex Gateway — Policy Engine Schemas (Phase 9C).

Defines the declarative team policy structure and the global default policy.

Design:
  - TeamPolicy accepts partial input — only the sections a team specifies are
    stored.  Unspecified sections fall back to the global default at resolution
    time.
  - ResolvedPolicy is always fully populated — all sections present — so
    downstream consumers never need to handle None.
  - Extra fields are forbidden on both models so that typos in section names
    (e.g. "routng") are rejected with a validation error rather than silently
    dropped.

Accepted values:
  routing.strategy : manual | auto | lowest_cost | lowest_latency |
                     best_available | capability_based
  fallback.enabled : bool
  budget.action    : BLOCK | WARN | DOWNGRADE  (normalised to upper-case)
  cache.enabled    : bool
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator


# ── Section schemas ───────────────────────────────────────────────────────────


class RoutingPolicy(BaseModel):
    """Routing section of a team policy."""

    model_config = ConfigDict(extra="forbid")

    strategy: Literal[
        "manual",
        "auto",
        "lowest_cost",
        "lowest_latency",
        "best_available",
        "capability_based",
    ] = "auto"


class FallbackPolicy(BaseModel):
    """Fallback/failover section of a team policy."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True


class BudgetPolicySection(BaseModel):
    """Budget action section of a team policy."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["BLOCK", "WARN", "DOWNGRADE"] = "BLOCK"

    @field_validator("action", mode="before")
    @classmethod
    def normalise_action(cls, v: object) -> str:
        """Accept any case; store as upper-case."""
        if isinstance(v, str):
            return v.strip().upper()
        raise ValueError(f"budget.action must be a string, got {type(v).__name__}")


class CachePolicy(BaseModel):
    """Semantic cache section of a team policy."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False  # mirrors SEMANTIC_CACHE_ENABLED default (False)


# ── Input schema (partial — for PUT body) ─────────────────────────────────────


class TeamPolicyInput(BaseModel):
    """
    Input schema for PUT /api/v1/teams/{team_id}/policy.

    All sections are optional — an admin may supply only the sections they
    want to override.  Unspecified sections inherit from the global default.

    Strict: extra fields are forbidden so that typos like "routng" return a
    clear validation error instead of being silently ignored.
    """

    model_config = ConfigDict(extra="forbid")

    routing: Optional[RoutingPolicy] = None
    fallback: Optional[FallbackPolicy] = None
    budget: Optional[BudgetPolicySection] = None
    cache: Optional[CachePolicy] = None


# ── Resolved (fully merged) schema ────────────────────────────────────────────


class ResolvedPolicy(BaseModel):
    """
    Fully-merged, immutable policy produced by PolicyResolver.

    All sections are always present.  Downstream services (ChatService,
    RoutingEngine, ReliabilityExecutor, SemanticCache) receive this object
    and never need to handle Optional sections.

    source:
      "global" — no team override; global default used.
      "team"   — at least one section came from the team's stored policy.
    """

    model_config = ConfigDict(frozen=True)

    routing: RoutingPolicy
    fallback: FallbackPolicy
    budget: BudgetPolicySection
    cache: CachePolicy
    source: Literal["global", "team"]


# ── Global default ─────────────────────────────────────────────────────────────

GLOBAL_DEFAULT_POLICY = ResolvedPolicy(
    routing=RoutingPolicy(strategy="auto"),       # settings.routing_default_mode
    fallback=FallbackPolicy(enabled=True),         # request.failover_enabled default
    budget=BudgetPolicySection(action="BLOCK"),    # Budget.policy default / budget_default_policy
    cache=CachePolicy(enabled=False),              # SEMANTIC_CACHE_ENABLED default
    source="global",
)
