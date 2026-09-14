"""
Cortex Gateway — Budget Pydantic Schemas (Phase 6).

Request/response schemas for budget CRUD and usage metadata.

Security rules:
  - `reserved` is an internal field and never returned in API responses.
  - Only `remaining_amount` (derived) is optionally exposed.
  - Budget management requires admin role (enforced in endpoints).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


BudgetPeriod = Literal["daily", "weekly", "monthly"]
BudgetPolicy = Literal["BLOCK", "WARN", "DOWNGRADE"]


class BudgetCreate(BaseModel):
    """Request body for creating a team budget."""

    limit_amount: float = Field(
        ...,
        gt=0,
        description="Maximum spend in USD for the period.",
    )
    period: BudgetPeriod = Field(
        "monthly",
        description="Billing period: 'daily', 'weekly', or 'monthly'.",
    )
    policy: BudgetPolicy = Field(
        "BLOCK",
        description=(
            "Enforcement policy when budget is exhausted: "
            "BLOCK (reject), WARN (allow + log), DOWNGRADE (use cheaper model)."
        ),
    )
    enabled: bool = Field(True, description="Whether the budget is active.")

    @field_validator("limit_amount")
    @classmethod
    def limit_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("limit_amount must be greater than zero.")
        return round(v, 6)


class BudgetUpdate(BaseModel):
    """Request body for updating an existing team budget (PATCH — all fields optional)."""

    limit_amount: Optional[float] = Field(
        None, gt=0, description="Updated spending limit in USD."
    )
    policy: Optional[BudgetPolicy] = Field(
        None, description="Updated enforcement policy."
    )
    enabled: Optional[bool] = Field(
        None, description="Enable or disable the budget."
    )
    # period cannot be changed without resetting usage — not supported in PATCH.
    # Create a new budget instead.


class BudgetResponse(BaseModel):
    """Safe budget metadata returned to API clients."""

    id: str
    team_id: str
    limit_amount: float
    current_usage: float
    period: str
    period_start: datetime
    period_end: datetime
    policy: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

    # Derived fields (computed, not stored directly)
    remaining_amount: float = Field(description="Available budget = limit - used - reserved.")
    usage_percentage: float = Field(description="Usage as % of limit.")

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_derived(cls, budget: object) -> "BudgetResponse":
        """Build response including derived fields from ORM object."""
        return cls(
            id=budget.id,  # type: ignore[attr-defined]
            team_id=budget.team_id,
            limit_amount=budget.limit_amount,
            current_usage=budget.current_usage,
            period=budget.period,
            period_start=budget.period_start,
            period_end=budget.period_end,
            policy=budget.policy,
            enabled=budget.enabled,
            created_at=budget.created_at,
            updated_at=budget.updated_at,
            remaining_amount=budget.remaining_amount,
            usage_percentage=budget.usage_percentage,
        )
