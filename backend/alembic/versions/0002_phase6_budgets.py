"""Phase 6 — Create budgets table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-14

Budget table supports team-level spending limits with:
  - Configurable periods (daily/weekly/monthly)
  - Atomic reservation via `reserved` column
  - Policy enforcement (BLOCK/WARN/DOWNGRADE)
  - Lazy rollover (period_start/period_end tracks current window)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create the budgets table.

    Foreign key: budgets.team_id → teams.id (CASCADE DELETE)
    Unique constraint: one budget per team
    Indexes: team_id (lookup), period_end (rollover scan)
    """
    op.create_table(
        "budgets",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("team_id", sa.String(36), nullable=False),
        # Spending limits
        sa.Column("limit_amount", sa.Float, nullable=False),
        sa.Column("current_usage", sa.Float, nullable=False, server_default="0.0"),
        sa.Column(
            "reserved",
            sa.Float,
            nullable=False,
            server_default="0.0",
            comment="Amount reserved by in-flight requests, not yet reconciled.",
        ),
        # Period management
        sa.Column("period", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        # Policy
        sa.Column("policy", sa.String(20), nullable=False, server_default="BLOCK"),
        # Flags
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        # Timestamps
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
            name="fk_budgets_team_id",
        ),
    )

    # One active budget per team
    op.create_unique_constraint("uq_budgets_team_id", "budgets", ["team_id"])

    # Index for team_id lookup (most common query pattern)
    op.create_index("ix_budgets_team_id", "budgets", ["team_id"])

    # Index for period_end (used in rollover check)
    op.create_index("ix_budgets_period_end", "budgets", ["period_end"])


def downgrade() -> None:
    """Drop the budgets table."""
    op.drop_index("ix_budgets_period_end", table_name="budgets")
    op.drop_index("ix_budgets_team_id", table_name="budgets")
    op.drop_constraint("uq_budgets_team_id", "budgets", type_="unique")
    op.drop_table("budgets")
