"""Phase 6 (Gap 2) — Create team_rate_limits table.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-14

Adds per-team rate limit overrides. NULL columns = inherit global default.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the team_rate_limits table."""
    op.create_table(
        "team_rate_limits",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("team_id", sa.String(36), nullable=False),
        # Nullable overrides — NULL = use global default from settings
        sa.Column(
            "requests_per_minute",
            sa.Integer,
            nullable=True,
            comment="Max requests per 60-second window. NULL = global default.",
        ),
        sa.Column(
            "requests_per_hour",
            sa.Integer,
            nullable=True,
            comment="Max requests per 3600-second window. NULL = disabled.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Foreign key: cascade delete when team is removed
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
            ondelete="CASCADE",
            name="fk_team_rate_limits_team_id",
        ),
    )

    # One row per team
    op.create_unique_constraint(
        "uq_team_rate_limits_team_id", "team_rate_limits", ["team_id"]
    )

    # Index for team_id lookup
    op.create_index(
        "ix_team_rate_limits_team_id", "team_rate_limits", ["team_id"]
    )


def downgrade() -> None:
    """Drop the team_rate_limits table."""
    op.drop_index("ix_team_rate_limits_team_id", table_name="team_rate_limits")
    op.drop_constraint(
        "uq_team_rate_limits_team_id", "team_rate_limits", type_="unique"
    )
    op.drop_table("team_rate_limits")
