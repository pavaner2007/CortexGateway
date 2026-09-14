"""
Cortex Gateway — Auth ORM Models (Phase 5).

SQLAlchemy 2.x declarative models for:
  - Organization  (top-level tenant)
  - Team          (belongs to one organization)
  - APIKey        (belongs to one team)

Relationships:
  Organization 1──N Team
  Team         1──N APIKey

Cascade rules:
  Deleting an organization cascades to its teams.
  Deleting a team cascades to its API keys.
  This ensures no orphaned rows exist.

Security:
  key_hash is stored (HMAC-SHA256); plaintext keys are NEVER stored.
  key_prefix is a short non-secret identifier for display/logs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def _now_utc() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    """Generate a new UUID4 string."""
    return str(uuid.uuid4())


class Organization(Base):
    """
    Top-level tenant entity.

    Every team and API key traces back to exactly one organization.
    The slug must be globally unique and is used in URL paths.
    """

    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_new_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now_utc
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now_utc, onupdate=_now_utc
    )

    # Relationships
    teams: Mapped[List["Team"]] = relationship(
        "Team",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        Index("ix_organizations_slug", "slug"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Organization id={self.id!r} slug={self.slug!r}>"


class Team(Base):
    """
    A team belongs to exactly one organization.

    The (organization_id, slug) pair must be unique — the same slug
    may exist in different organizations.
    """

    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_new_uuid
    )
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now_utc
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now_utc, onupdate=_now_utc
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="teams"
    )
    api_keys: Mapped[List["APIKey"]] = relationship(
        "APIKey",
        back_populates="team",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_teams_org_slug"),
        Index("ix_teams_organization_id", "organization_id"),
        Index("ix_teams_org_slug", "organization_id", "slug"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Team id={self.id!r} slug={self.slug!r} org={self.organization_id!r}>"


class APIKey(Base):
    """
    An API key grants service-to-service access on behalf of a team.

    Security invariants:
    - key_hash stores HMAC-SHA256(plaintext_key, pepper). Plaintext is NEVER stored.
    - key_prefix stores the first ~20 chars of the key for identification only.
    - Revocation is soft-delete via revoked_at timestamp.
    - Expiration is enforced at authentication time via expires_at.

    Roles:
    - 'admin'  — full management permissions within the organization
    - 'member' — chat only; cannot create teams/keys or list key metadata
    """

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_new_uuid
    )
    team_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now_utc
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    team: Mapped["Team"] = relationship("Team", back_populates="api_keys")

    __table_args__ = (
        Index("ix_api_keys_team_id", "team_id"),
        Index("ix_api_keys_key_prefix", "key_prefix"),
        Index("ix_api_keys_key_hash", "key_hash"),
    )

    @property
    def is_active(self) -> bool:
        """Return True if the key is neither revoked nor expired."""
        from datetime import timezone as tz
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None:
            return datetime.now(tz.utc) < self.expires_at
        return True

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<APIKey id={self.id!r} prefix={self.key_prefix!r} "
            f"role={self.role!r} team={self.team_id!r}>"
        )
