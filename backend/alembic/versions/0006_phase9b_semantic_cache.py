"""Phase 9B — Semantic Cache: add cache_hit to request_logs.

Revision ID: 0006_phase9b_semantic_cache
Revises: 0005_phase9a_model_registry
Create Date: 2026-09-19

Changes:
  - Add ``cache_hit`` (BOOLEAN NOT NULL DEFAULT FALSE) to ``request_logs``.
    True when the response was served from the semantic cache without calling
    a provider; False for all normal (non-cached) requests.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_phase9b_semantic_cache"
down_revision: str = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add cache_hit column with a safe default so existing rows are not NULL.
    op.add_column(
        "request_logs",
        sa.Column(
            "cache_hit",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("request_logs", "cache_hit")
