"""Create request_logs table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-16

request_logs provides persistent, per-request audit data used by:
  - Analytics APIs (GET /api/v1/analytics/*)
  - Cost attribution / budget reporting
  - Reliability forensics (retry / failover patterns)
  - Latency p50/p95/p99 over historical windows

One row per completed client request.
A request with 2 retries + 1 failover = 1 row (aggregated).
Requests rejected before routing (rate-limit, budget-block) also get
a row; provider/model are NULL in those cases.

Foreign keys use ON DELETE SET NULL so deleting a team or organization
does not cascade-delete historical audit records.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the request_logs table with all indexes."""
    op.create_table(
        "request_logs",

        # ── Identity ────────────────────────────────────────────────────────
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("request_id", sa.String(255), nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=True),

        # ── Tenant context ────────────────────────────────────────────────
        sa.Column("organization_id", sa.String(36), nullable=True),
        sa.Column("team_id", sa.String(36), nullable=True),

        # ── Routing ───────────────────────────────────────────────────────
        sa.Column("provider", sa.String(100), nullable=True),
        sa.Column("model", sa.String(255), nullable=True),
        sa.Column("routing_mode", sa.String(50), nullable=True),

        # ── Outcome ───────────────────────────────────────────────────────
        sa.Column("status", sa.String(50), nullable=False, server_default="success"),
        sa.Column("http_status_code", sa.Integer, nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),

        # ── Performance ───────────────────────────────────────────────────
        sa.Column("latency_ms", sa.Float, nullable=True),

        # ── Token usage ───────────────────────────────────────────────────
        sa.Column("prompt_tokens", sa.Integer, nullable=True),
        sa.Column("completion_tokens", sa.Integer, nullable=True),
        sa.Column("total_tokens", sa.Integer, nullable=True),

        # ── Cost ──────────────────────────────────────────────────────────
        sa.Column("estimated_cost", sa.Float, nullable=True),
        sa.Column("actual_cost", sa.Float, nullable=True),

        # ── Reliability ───────────────────────────────────────────────────
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failover_triggered", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("failover_from_provider", sa.String(100), nullable=True),
        sa.Column("failover_to_provider", sa.String(100), nullable=True),
        sa.Column("circuit_breaker_state", sa.String(20), nullable=True),

        # ── Budget ────────────────────────────────────────────────────────
        sa.Column("budget_policy_applied", sa.String(20), nullable=True),
        sa.Column("budget_action", sa.String(20), nullable=True),

        # ── Timestamp ─────────────────────────────────────────────────────
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),

        # ── Foreign keys (SET NULL — preserve audit log on deletion) ──────
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="SET NULL",
            name="fk_request_logs_organization_id",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
            ondelete="SET NULL",
            name="fk_request_logs_team_id",
        ),
    )

    # ── Single-column indexes ──────────────────────────────────────────────
    op.create_index("ix_request_logs_request_id", "request_logs", ["request_id"])
    op.create_index("ix_request_logs_created_at", "request_logs", ["created_at"])
    op.create_index("ix_request_logs_team_id", "request_logs", ["team_id"])
    op.create_index("ix_request_logs_organization_id", "request_logs", ["organization_id"])
    op.create_index("ix_request_logs_provider", "request_logs", ["provider"])
    op.create_index("ix_request_logs_model", "request_logs", ["model"])
    op.create_index("ix_request_logs_status", "request_logs", ["status"])

    # ── Composite indexes for analytics range queries ──────────────────────
    op.create_index("ix_rl_org_created", "request_logs", ["organization_id", "created_at"])
    op.create_index("ix_rl_team_created", "request_logs", ["team_id", "created_at"])
    op.create_index("ix_rl_provider_created", "request_logs", ["provider", "created_at"])


def downgrade() -> None:
    """Drop the request_logs table and all its indexes."""
    op.drop_index("ix_rl_provider_created", table_name="request_logs")
    op.drop_index("ix_rl_team_created", table_name="request_logs")
    op.drop_index("ix_rl_org_created", table_name="request_logs")
    op.drop_index("ix_request_logs_status", table_name="request_logs")
    op.drop_index("ix_request_logs_model", table_name="request_logs")
    op.drop_index("ix_request_logs_provider", table_name="request_logs")
    op.drop_index("ix_request_logs_organization_id", table_name="request_logs")
    op.drop_index("ix_request_logs_team_id", table_name="request_logs")
    op.drop_index("ix_request_logs_created_at", table_name="request_logs")
    op.drop_index("ix_request_logs_request_id", table_name="request_logs")
    op.drop_table("request_logs")
