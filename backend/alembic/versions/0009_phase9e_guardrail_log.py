"""Phase 9E — Add guardrail observation columns to request_logs.

Adds two nullable columns to the request_logs table:

  guardrails_triggered  VARCHAR(500)  — JSON-encoded list of triggered guardrail
                                        names, e.g. '["pii","injection"]'.
                                        Stored as VARCHAR for compatibility with
                                        both PostgreSQL (production) and SQLite
                                        (test fixtures).  NULL for clean requests.
                                        Never contains matched PII values,
                                        prompt text, or any sensitive content.

  guardrail_action      VARCHAR(20)   — Aggregate action applied: "warn" | "block".
                                        NULL for requests where no guardrail fired.

Semantics:
  Clean request:           both columns NULL.
  Warned request:          guardrails_triggered='["pii"]', guardrail_action='warn'.
  Blocked request:         guardrails_triggered='["pii","injection"]',
                           guardrail_action='block'.

Both columns are nullable — existing rows keep NULL values (backward compatible).

Revision ID: 0009
Revises: 0008
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_phase9e_guardrail_log"
down_revision = "0008_phase9d_experiment_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "request_logs",
        sa.Column("guardrails_triggered", sa.String(500), nullable=True),
    )
    op.add_column(
        "request_logs",
        sa.Column("guardrail_action", sa.String(20), nullable=True),
    )
    # Index on guardrail_action for analytics queries
    # (e.g. "how many requests were blocked this week?")
    op.create_index(
        "ix_request_logs_guardrail_action",
        "request_logs",
        ["guardrail_action"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_request_logs_guardrail_action", table_name="request_logs")
    op.drop_column("request_logs", "guardrail_action")
    op.drop_column("request_logs", "guardrails_triggered")
