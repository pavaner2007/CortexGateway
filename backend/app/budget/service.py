"""
Cortex Gateway — Budget Service (Phase 6).

Implements:
  - Budget CRUD (admin only)
  - Period rollover (lazy, on access)
  - Atomic budget reservation (PostgreSQL SELECT FOR UPDATE)
  - Budget reconciliation (after provider call)
  - BLOCK / WARN / DOWNGRADE policy enforcement

Concurrency protection:
  check_and_reserve() uses SELECT FOR UPDATE to lock the budget row before
  reading or modifying it. This prevents two concurrent requests from both
  reading the same remaining balance and both being allowed to overspend.

Rollover strategy (lazy):
  On each access, if period_end < utcnow, the service resets current_usage=0,
  reserved=0, and advances period_start/period_end. The rollover happens inside
  the same SELECT FOR UPDATE lock, so concurrent rollovers cannot fire twice.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.budget.exceptions import BudgetConfigurationError, BudgetExceeded
from app.budget.models import Budget
from app.budget.schemas import BudgetCreate, BudgetUpdate
from app.core.logging import logger


class BudgetService:
    """Application-layer service for team-level budget management."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Period Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _compute_period_end(period: str, period_start: datetime) -> datetime:
        """Compute period_end from period_start based on the period type."""
        if period == "daily":
            return period_start + timedelta(days=1)
        elif period == "weekly":
            return period_start + timedelta(weeks=1)
        elif period == "monthly":
            # Advance ~30 days then snap to the 1st of the next month
            next_month = period_start.replace(day=1) + timedelta(days=32)
            return next_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            raise BudgetConfigurationError(f"Unknown budget period: {period!r}")

    # ── CRUD ───────────────────────────────────────────────────────────────────

    async def get_budget(self, team_id: str) -> Optional[Budget]:
        """Return the active budget for a team, or None if none exists."""
        result = await self._session.execute(
            select(Budget).where(Budget.team_id == team_id)
        )
        return result.scalar_one_or_none()

    async def create_budget(
        self,
        team_id: str,
        data: BudgetCreate,
    ) -> Budget:
        """Create a new team budget. Raises if a budget already exists for the team."""
        existing = await self.get_budget(team_id)
        if existing is not None:
            raise BudgetConfigurationError(
                f"A budget already exists for team {team_id!r}. "
                "Use PATCH to update or DELETE to remove it first."
            )
        now = datetime.now(timezone.utc)
        period_end = self._compute_period_end(data.period, now)
        budget = Budget(
            team_id=team_id,
            limit_amount=data.limit_amount,
            current_usage=0.0,
            reserved=0.0,
            period=data.period,
            period_start=now,
            period_end=period_end,
            policy=data.policy,
            enabled=data.enabled,
        )
        self._session.add(budget)
        await self._session.commit()
        await self._session.refresh(budget)
        logger.info(
            "Budget created",
            team_id=team_id,
            limit=data.limit_amount,
            period=data.period,
            policy=data.policy,
        )
        return budget

    async def update_budget(
        self,
        team_id: str,
        data: BudgetUpdate,
    ) -> Budget:
        """Update an existing budget's limit, policy, or enabled flag."""
        budget = await self.get_budget(team_id)
        if budget is None:
            raise BudgetConfigurationError(
                f"No budget found for team {team_id!r}."
            )
        if data.limit_amount is not None:
            budget.limit_amount = data.limit_amount
        if data.policy is not None:
            budget.policy = data.policy
        if data.enabled is not None:
            budget.enabled = data.enabled
        budget.updated_at = datetime.now(timezone.utc)
        await self._session.commit()
        await self._session.refresh(budget)
        logger.info("Budget updated", team_id=team_id)
        return budget

    async def delete_budget(self, team_id: str) -> bool:
        """Delete the budget for a team. Returns True if deleted, False if not found."""
        budget = await self.get_budget(team_id)
        if budget is None:
            return False
        await self._session.delete(budget)
        await self._session.commit()
        logger.info("Budget deleted", team_id=team_id)
        return True

    # ── Rollover ───────────────────────────────────────────────────────────────

    def _apply_rollover_if_needed(self, budget: Budget) -> bool:
        """
        Check if the period has expired and reset usage if so.

        Must be called while holding a SELECT FOR UPDATE lock on the row
        to prevent concurrent rollovers.

        Returns True if rollover occurred.
        """
        if not budget.is_period_expired:
            return False

        now = datetime.now(timezone.utc)
        old_usage = budget.current_usage
        budget.current_usage = 0.0
        budget.reserved = 0.0
        budget.period_start = now
        budget.period_end = self._compute_period_end(budget.period, now)
        budget.updated_at = now

        logger.info(
            "Budget period rolled over",
            team_id=budget.team_id,
            old_usage=old_usage,
            new_period_end=budget.period_end.isoformat(),
        )
        return True

    # ── Reservation / Reconciliation ───────────────────────────────────────────

    async def check_and_reserve(
        self,
        team_id: str,
        estimated_cost: float,
        warning_threshold_percent: int = 80,
    ) -> Tuple[Optional[Budget], bool]:
        """
        Atomically check the budget and reserve the estimated cost.

        Uses SELECT FOR UPDATE to lock the budget row before reading or
        modifying it — preventing two concurrent requests from both seeing
        the same remaining balance and both being allowed through.

        Returns:
            (budget, budget_warning_raised) tuple.

        Raises:
            BudgetExceeded: If policy=BLOCK and estimated_cost would exceed limit.
        """
        # SELECT FOR UPDATE — row-level lock
        result = await self._session.execute(
            select(Budget)
            .where(Budget.team_id == team_id, Budget.enabled == True)  # noqa: E712
            .with_for_update()
        )
        budget = result.scalar_one_or_none()

        if budget is None:
            # No budget configured for this team — allow request
            return None, False

        # Lazy rollover inside the lock
        self._apply_rollover_if_needed(budget)

        budget_warning = False
        policy = budget.policy.upper()

        if policy == "BLOCK":
            # Reject if adding estimated_cost would exceed limit (considering reserved)
            if (budget.current_usage + budget.reserved + estimated_cost) > budget.limit_amount:
                await self._session.rollback()
                raise BudgetExceeded(
                    message=(
                        f"Team budget exhausted. "
                        f"Remaining: ${budget.remaining_amount:.6f}, "
                        f"estimated cost: ${estimated_cost:.6f}."
                    ),
                    team_id=team_id,
                    remaining=budget.remaining_amount,
                )
            # Reserve the amount
            budget.reserved += estimated_cost

        elif policy == "WARN":
            # Always allow; reserve for reconciliation
            budget.reserved += estimated_cost
            # Emit warning if budget threshold is crossed
            usage_after = budget.current_usage + estimated_cost
            usage_pct = (usage_after / budget.limit_amount * 100) if budget.limit_amount > 0 else 0
            if usage_after > budget.limit_amount:
                budget_warning = True
                logger.warning(
                    "budget_threshold_crossed",
                    event="budget_exceeded_warn_policy",
                    team_id=team_id,
                    usage=budget.current_usage,
                    limit=budget.limit_amount,
                    policy="WARN",
                )
            elif usage_pct >= warning_threshold_percent:
                budget_warning = True
                logger.warning(
                    "budget_threshold_crossed",
                    event="budget_warning_threshold",
                    team_id=team_id,
                    usage_pct=round(usage_pct, 1),
                    threshold_pct=warning_threshold_percent,
                    team_id_=team_id,
                    policy="WARN",
                )

        elif policy == "DOWNGRADE":
            # Caller (ChatService) handles downgrade logic before calling us.
            # By the time we reach here, the estimated_cost fits in the budget.
            if (budget.current_usage + budget.reserved + estimated_cost) > budget.limit_amount:
                await self._session.rollback()
                raise BudgetExceeded(
                    message="No cheaper provider found within budget.",
                    team_id=team_id,
                    remaining=budget.remaining_amount,
                )
            budget.reserved += estimated_cost

        budget.updated_at = datetime.now(timezone.utc)
        await self._session.commit()
        await self._session.refresh(budget)
        return budget, budget_warning

    async def reconcile(
        self,
        team_id: str,
        estimated_cost: float,
        actual_cost: float,
    ) -> Optional[Budget]:
        """
        Reconcile the budget after provider execution.

        Releases the reservation and charges the actual cost.

        If provider failed (actual_cost=0 and we couldn't determine usage),
        the reservation is fully released (no charge for failed calls).

        Thread-safe: uses SELECT FOR UPDATE.
        """
        result = await self._session.execute(
            select(Budget)
            .where(Budget.team_id == team_id, Budget.enabled == True)  # noqa: E712
            .with_for_update()
        )
        budget = result.scalar_one_or_none()

        if budget is None:
            return None

        # Release reservation and charge actual cost
        budget.reserved = max(0.0, budget.reserved - estimated_cost)
        budget.current_usage = max(0.0, budget.current_usage + actual_cost)
        budget.updated_at = datetime.now(timezone.utc)

        await self._session.commit()
        await self._session.refresh(budget)

        logger.info(
            "Budget reconciled",
            team_id=team_id,
            estimated=estimated_cost,
            actual=actual_cost,
            total_usage=budget.current_usage,
            remaining=budget.remaining_amount,
        )
        return budget

    async def release_reservation(
        self,
        team_id: str,
        estimated_cost: float,
    ) -> None:
        """
        Release a reservation without charging any usage (e.g. provider failure).

        Called when the provider fails before returning any usable output,
        ensuring no phantom budget charges from failed requests.
        """
        result = await self._session.execute(
            select(Budget)
            .where(Budget.team_id == team_id, Budget.enabled == True)  # noqa: E712
            .with_for_update()
        )
        budget = result.scalar_one_or_none()
        if budget is None:
            return

        budget.reserved = max(0.0, budget.reserved - estimated_cost)
        budget.updated_at = datetime.now(timezone.utc)
        await self._session.commit()
        logger.info(
            "Budget reservation released (provider failure)",
            team_id=team_id,
            released=estimated_cost,
        )
