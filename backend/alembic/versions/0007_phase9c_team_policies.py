"""Phase 9C — Policy Engine: create team_policies table.

Revision ID: 0007_phase9c_team_policies
Revises: 0006_phase9b_semantic_cache
Create Date: 2026-09-19

Changes:
  - Create ``team_policies`` table:
      id          VARCHAR(36) PK
      team_id     VARCHAR(36) FK→teams.id NOT NULL UNIQUE (CASCADE)
      policy      JSONB NOT NULL
      enabled     BOOLEAN NOT NULL DEFAULT TRUE
      created_at  TIMESTAMP WITH TIME ZONE NOT NULL
      updated_at  TIMESTAMP WITH TIME ZONE NOT NULL

  No auto-backfill of existing Budget.policy values.
  Teams without a policy row use the global default (BLOCK / auto / failover /
  cache-off), which matches the pre-9C Budget.policy default of BLOCK.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "0007_phase9c_team_policies"
down_revision: str = "0006_phase9b_semantic_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "team_policies",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("team_id", sa.String(36), nullable=False),
        sa.Column("policy", JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
            name="fk_team_policies_team_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", name="uq_team_policies_team_id"),
    )
    op.create_index("ix_team_policies_team_id", "team_policies", ["team_id"])


def downgrade() -> None:
    op.drop_index("ix_team_policies_team_id", table_name="team_policies")
    op.drop_table("team_policies")
