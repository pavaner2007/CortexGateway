"""Phase 9D — Add experiment tracking columns to request_logs.

Adds three nullable columns to the request_logs table:
  experiment_id      VARCHAR(255) — stable experiment identifier
  experiment_version INTEGER       — version at time of assignment
  experiment_arm     VARCHAR(255) — name of arm assigned by the experiment

These are distinct from provider/model which record the ACTUAL serving
provider. experiment_arm is the ASSIGNED arm; in a failover scenario
these will differ (see Phase 9D spec section 25-26).

NULL for:
  - Requests with no active experiment
  - Cache hits (experiment assignment skipped)

Revision ID: 0008
Revises: 0007
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_phase9d_experiment_log"
down_revision = "0007_phase9c_team_policies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "request_logs",
        sa.Column("experiment_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "request_logs",
        sa.Column("experiment_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "request_logs",
        sa.Column("experiment_arm", sa.String(255), nullable=True),
    )
    # Index on experiment_id for analytics grouping queries
    op.create_index(
        "ix_request_logs_experiment_id",
        "request_logs",
        ["experiment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_request_logs_experiment_id", table_name="request_logs")
    op.drop_column("request_logs", "experiment_arm")
    op.drop_column("request_logs", "experiment_version")
    op.drop_column("request_logs", "experiment_id")
