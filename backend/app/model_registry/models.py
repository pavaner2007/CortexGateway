"""
Cortex Gateway — Model Registry ORM Model (Phase 9A).

Persistent source of truth for model metadata: pricing, capabilities,
context window, enabled state. Replaces the static _DEFAULT_CATALOG
in routing/metadata.py.

Table: model_registry
  - Primary key: UUID string
  - Unique constraint: (provider, model_name)
  - Capabilities: JSONB list of strings (["text","vision","json",...])
  - Indexes: provider, enabled
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ModelRegistryEntry(Base):
    """
    Persistent model registry entry.

    Each row describes one (provider, model_name) combination:
    its pricing, capability flags, context window, and enabled state.

    Phase 3 routing and Phase 6 cost calculation both consume this table
    via ModelMetadataCatalog.
    """

    __tablename__ = "model_registry"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_new_uuid
    )
    provider: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    model_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    display_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    # Pricing — split input/output per Phase 6 requirement
    # Stored as NUMERIC-precision floats; Python uses float
    input_cost_per_1k: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    output_cost_per_1k: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    # Capabilities — stored as a JSONB list of strings
    # e.g. ["text", "vision", "json", "code", "tools"]
    # Validated on write via Pydantic schema; read directly as list by Phase 3.
    capabilities: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )

    # Context window in tokens
    context_window: Mapped[int] = mapped_column(
        Integer, nullable=False, default=8192
    )

    # Baseline cold-start latency used by the routing scorer
    baseline_latency_ms: Mapped[float] = mapped_column(
        Float, nullable=False, default=500.0
    )

    # Admin can disable a model without deleting it
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )

    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now_utc
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now_utc, onupdate=_now_utc
    )

    __table_args__ = (
        UniqueConstraint("provider", "model_name", name="uq_model_registry_provider_model"),
        Index("ix_model_registry_provider", "provider"),
        Index("ix_model_registry_enabled", "enabled"),
    )

    @property
    def cost_per_1k_tokens(self) -> float:
        """Blended cost for Phase 3 routing scorer (average of input/output)."""
        return (self.input_cost_per_1k + self.output_cost_per_1k) / 2.0

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ModelRegistryEntry provider={self.provider!r} "
            f"model={self.model_name!r} enabled={self.enabled}>"
        )
