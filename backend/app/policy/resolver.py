"""
Cortex Gateway — Policy Resolver (Phase 9C).

Resolves the effective policy for a team exactly once per request.

Resolution order:
  GLOBAL_DEFAULT_POLICY
        ↓  (merged with team's stored sections — team wins on overlap)
  ResolvedPolicy

The result is an immutable ResolvedPolicy object passed to all downstream
subsystems in the same request.  No further DB lookups are needed.

Failure handling:
  If the DB is unavailable, PolicyResolver falls back to the global default
  and logs a warning.  It never silently applies the wrong team's policy.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.policy.schemas import (
    BudgetPolicySection,
    CachePolicy,
    FallbackPolicy,
    GLOBAL_DEFAULT_POLICY,
    GuardrailsPolicy,
    ResolvedPolicy,
    RoutingPolicy,
    TeamPolicyInput,
)
from app.policy.service import PolicyService


class PolicyResolver:
    """Resolves the effective ResolvedPolicy for a team."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve(self, team_id: Optional[str]) -> ResolvedPolicy:
        """
        Return the effective ResolvedPolicy for a team.

        If team_id is None or no policy row exists → global default.
        If a policy row exists → merge team overrides onto the global default.

        Never raises: DB failures degrade gracefully to global default.
        """
        if not team_id:
            return GLOBAL_DEFAULT_POLICY

        try:
            svc = PolicyService(self._session)
            raw = await svc.get_policy_dict(team_id)
        except Exception as exc:
            logger.warning(
                "PolicyResolver: DB lookup failed — using global default",
                team_id=team_id,
                error=str(exc),
            )
            return GLOBAL_DEFAULT_POLICY

        if raw is None:
            return GLOBAL_DEFAULT_POLICY

        # Merge: start from global defaults, apply team overrides section-by-section.
        return self._merge(raw, team_id)

    @staticmethod
    def _merge(raw: dict, team_id: str) -> ResolvedPolicy:
        """
        Merge a partial raw policy dict onto the global default.

        Each section is independently resolved:
          - If the team specified the section → use team value.
          - Otherwise → use global default for that section.
        """
        try:
            partial = TeamPolicyInput.model_validate(raw)
        except Exception as exc:
            logger.warning(
                "PolicyResolver: stored policy failed validation — using global default",
                team_id=team_id,
                error=str(exc),
            )
            return GLOBAL_DEFAULT_POLICY

        g = GLOBAL_DEFAULT_POLICY

        routing = partial.routing if partial.routing is not None else g.routing
        fallback = partial.fallback if partial.fallback is not None else g.fallback
        budget = partial.budget if partial.budget is not None else g.budget
        cache = partial.cache if partial.cache is not None else g.cache
        # Phase 9D: experiment is pass-through — use team's value (may be None)
        experiment = partial.experiment  # None means no active experiment
        # Phase 9E: guardrails — use team's section if set; global default (all-off) otherwise
        guardrails = partial.guardrails if partial.guardrails is not None else g.guardrails

        resolved = ResolvedPolicy(
            routing=routing,
            fallback=fallback,
            budget=budget,
            cache=cache,
            source="team",
            experiment=experiment,
            guardrails=guardrails,
        )

        logger.debug(
            "Policy resolved",
            team_id=team_id,
            source="team",
            routing=resolved.routing.strategy,
            fallback=resolved.fallback.enabled,
            budget=resolved.budget.action,
            cache=resolved.cache.enabled,
        )
        return resolved
