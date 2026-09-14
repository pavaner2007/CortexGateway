"""
Cortex Gateway — Auth Pydantic Schemas (Phase 5).

Safe request/response models for:
  - Organization CRUD
  - Team CRUD
  - API Key lifecycle
  - Bootstrap
  - RequestContext (dataclass propagated via ContextVar)

Security rules enforced here:
  - key_hash is NEVER included in any response schema.
  - Plaintext API key appears ONLY in APIKeyCreatedResponse (creation only).
  - All response models use explicit field lists (no ORM passthrough).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ── Request Context ───────────────────────────────────────────────────────────


@dataclass
class RequestContext:
    """
    Authenticated request context propagated via ContextVar.

    Available to all downstream layers (ChatService, Phase 3 Router,
    Phase 4 Reliability, logging) without parameter threading.

    Phase 6 will read:
        request_context.team_id   → rate limiting / budgets
        request_context.org_id    → org-level quotas
    """

    organization_id: str
    team_id: str
    api_key_id: str
    role: str  # "admin" | "member"


# ── Organization Schemas ──────────────────────────────────────────────────────


class OrganizationCreate(BaseModel):
    """Request body for creating an organization."""

    name: str = Field(..., min_length=1, max_length=255, description="Organization display name.")
    slug: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9-]+$",
        description="URL-safe slug. Lowercase letters, digits, hyphens only.",
    )


class OrganizationResponse(BaseModel):
    """Safe organization metadata returned to API clients."""

    id: str
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Team Schemas ──────────────────────────────────────────────────────────────


class TeamCreate(BaseModel):
    """Request body for creating a team."""

    name: str = Field(..., min_length=1, max_length=255, description="Team display name.")
    slug: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9-]+$",
        description="URL-safe slug. Unique within the organization.",
    )


class TeamResponse(BaseModel):
    """Safe team metadata returned to API clients."""

    id: str
    organization_id: str
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TeamListResponse(BaseModel):
    """List of teams for an organization."""

    teams: List[TeamResponse]


# ── API Key Schemas ───────────────────────────────────────────────────────────


class APIKeyCreate(BaseModel):
    """Request body for creating an API key."""

    name: str = Field(..., min_length=1, max_length=255, description="Descriptive name for this key.")
    role: Literal["admin", "member"] = Field(
        "member",
        description="Role granted to this key: 'admin' or 'member'.",
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="Optional expiration datetime (UTC). Key never expires if omitted.",
    )

    @field_validator("name")
    @classmethod
    def name_not_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("API key name cannot be blank.")
        return v.strip()


class APIKeyResponse(BaseModel):
    """
    Safe API key metadata.

    key_hash is NEVER included.
    Plaintext key is NOT included (use APIKeyCreatedResponse for creation).
    """

    id: str
    name: str
    key_prefix: str
    role: str
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    created_at: datetime
    last_used_at: Optional[datetime]

    model_config = {"from_attributes": True}


class APIKeyCreatedResponse(BaseModel):
    """
    Returned ONLY once immediately after successful key creation.

    The `key` field contains the plaintext secret. After this response
    is sent, the plaintext key is gone forever. Users must create a new
    key if they lose it.
    """

    id: str
    name: str
    key: str = Field(description="Plaintext API key. Displayed ONCE. Store it securely.")
    key_prefix: str
    role: str
    expires_at: Optional[datetime]
    created_at: datetime


class APIKeyListResponse(BaseModel):
    """List of API key metadata for a team."""

    keys: List[APIKeyResponse]


# ── Bootstrap Schemas ─────────────────────────────────────────────────────────


class BootstrapRequest(BaseModel):
    """Request body for the one-time bootstrap endpoint."""

    organization_name: str = Field(..., min_length=1, max_length=255)
    organization_slug: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9-]+$",
    )
    team_name: str = Field(..., min_length=1, max_length=255)
    team_slug: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9-]+$",
    )
    admin_key_name: str = Field(..., min_length=1, max_length=255)


class BootstrapResponse(BaseModel):
    """
    Bootstrap response containing the first admin API key.

    The `admin_key` plaintext is returned ONCE. Subsequent calls to the
    bootstrap endpoint are rejected if an organization already exists.
    """

    organization: OrganizationResponse
    team: TeamResponse
    admin_key: APIKeyCreatedResponse
    message: str = (
        "Bootstrap successful. Store the admin_key securely — it will not be shown again."
    )
