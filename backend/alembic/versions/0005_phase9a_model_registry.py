"""Create model_registry table and seed default catalog.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-18

model_registry is the persistent source of truth for model metadata:
  - pricing (input/output cost per 1k tokens)
  - capabilities (JSON list of capability strings)
  - context window
  - enabled flag

Phase 3 routing and Phase 6 cost calculation both consume this table.

Seed data mirrors the static _DEFAULT_CATALOG previously in
routing/metadata.py so existing deployments work immediately without
manual data entry.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision: str = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Seed data — mirrors _DEFAULT_CATALOG exactly ──────────────────────────────
_SEED_MODELS = [
    # Gemini
    {
        "id": str(uuid.uuid4()),
        "provider": "gemini",
        "model_name": "gemini-1.5-flash",
        "display_name": "Gemini 1.5 Flash",
        "input_cost_per_1k": 0.000075,
        "output_cost_per_1k": 0.000300,
        "capabilities": ["text", "vision", "json", "code"],
        "context_window": 1000000,
        "baseline_latency_ms": 450.0,
        "enabled": True,
    },
    {
        "id": str(uuid.uuid4()),
        "provider": "gemini",
        "model_name": "gemini-1.5-pro",
        "display_name": "Gemini 1.5 Pro",
        "input_cost_per_1k": 0.001250,
        "output_cost_per_1k": 0.005000,
        "capabilities": ["text", "vision", "json", "code", "complex_reasoning"],
        "context_window": 2000000,
        "baseline_latency_ms": 900.0,
        "enabled": True,
    },
    {
        "id": str(uuid.uuid4()),
        "provider": "gemini",
        "model_name": "gemini-2.0-flash",
        "display_name": "Gemini 2.0 Flash",
        "input_cost_per_1k": 0.000100,
        "output_cost_per_1k": 0.000400,
        "capabilities": ["text", "vision", "json", "code", "tools"],
        "context_window": 1000000,
        "baseline_latency_ms": 350.0,
        "enabled": True,
    },
    {
        "id": str(uuid.uuid4()),
        "provider": "gemini",
        "model_name": "gemini-2.5-flash",
        "display_name": "Gemini 2.5 Flash",
        "input_cost_per_1k": 0.000100,
        "output_cost_per_1k": 0.000400,
        "capabilities": ["text", "vision", "json", "code", "tools"],
        "context_window": 1000000,
        "baseline_latency_ms": 350.0,
        "enabled": True,
    },
    # Groq
    {
        "id": str(uuid.uuid4()),
        "provider": "groq",
        "model_name": "llama-3.3-70b-versatile",
        "display_name": "LLaMA 3.3 70B Versatile",
        "input_cost_per_1k": 0.000590,
        "output_cost_per_1k": 0.000790,
        "capabilities": ["text", "json", "code", "tools"],
        "context_window": 128000,
        "baseline_latency_ms": 180.0,
        "enabled": True,
    },
    {
        "id": str(uuid.uuid4()),
        "provider": "groq",
        "model_name": "llama-3.1-8b-instant",
        "display_name": "LLaMA 3.1 8B Instant",
        "input_cost_per_1k": 0.000050,
        "output_cost_per_1k": 0.000080,
        "capabilities": ["text", "json", "code"],
        "context_window": 128000,
        "baseline_latency_ms": 90.0,
        "enabled": True,
    },
    {
        "id": str(uuid.uuid4()),
        "provider": "groq",
        "model_name": "llama3-8b-8192",
        "display_name": "LLaMA3 8B 8192",
        "input_cost_per_1k": 0.000050,
        "output_cost_per_1k": 0.000080,
        "capabilities": ["text", "json", "code"],
        "context_window": 8192,
        "baseline_latency_ms": 100.0,
        "enabled": True,
    },
    {
        "id": str(uuid.uuid4()),
        "provider": "groq",
        "model_name": "llama3-70b-8192",
        "display_name": "LLaMA3 70B 8192",
        "input_cost_per_1k": 0.000590,
        "output_cost_per_1k": 0.000790,
        "capabilities": ["text", "json", "code", "tools"],
        "context_window": 8192,
        "baseline_latency_ms": 220.0,
        "enabled": True,
    },
    {
        "id": str(uuid.uuid4()),
        "provider": "groq",
        "model_name": "mixtral-8x7b-32768",
        "display_name": "Mixtral 8x7B 32768",
        "input_cost_per_1k": 0.000240,
        "output_cost_per_1k": 0.000240,
        "capabilities": ["text", "json", "code"],
        "context_window": 32768,
        "baseline_latency_ms": 150.0,
        "enabled": True,
    },
    {
        "id": str(uuid.uuid4()),
        "provider": "groq",
        "model_name": "gemma2-9b-it",
        "display_name": "Gemma2 9B Instruct",
        "input_cost_per_1k": 0.000100,
        "output_cost_per_1k": 0.000100,
        "capabilities": ["text", "code"],
        "context_window": 8192,
        "baseline_latency_ms": 130.0,
        "enabled": True,
    },
    # Ollama (zero-cost by default)
    {
        "id": str(uuid.uuid4()),
        "provider": "ollama",
        "model_name": "llama3.2",
        "display_name": "LLaMA 3.2",
        "input_cost_per_1k": 0.0,
        "output_cost_per_1k": 0.0,
        "capabilities": ["text", "json", "code"],
        "context_window": 8192,
        "baseline_latency_ms": 300.0,
        "enabled": True,
    },
    {
        "id": str(uuid.uuid4()),
        "provider": "ollama",
        "model_name": "llama3.2:latest",
        "display_name": "LLaMA 3.2 (latest tag)",
        "input_cost_per_1k": 0.0,
        "output_cost_per_1k": 0.0,
        "capabilities": ["text", "json", "code"],
        "context_window": 8192,
        "baseline_latency_ms": 300.0,
        "enabled": True,
    },
    {
        "id": str(uuid.uuid4()),
        "provider": "ollama",
        "model_name": "llama3.2-vision",
        "display_name": "LLaMA 3.2 Vision",
        "input_cost_per_1k": 0.0,
        "output_cost_per_1k": 0.0,
        "capabilities": ["text", "vision", "code"],
        "context_window": 8192,
        "baseline_latency_ms": 450.0,
        "enabled": True,
    },
    {
        "id": str(uuid.uuid4()),
        "provider": "ollama",
        "model_name": "qwen2.5",
        "display_name": "Qwen 2.5",
        "input_cost_per_1k": 0.0,
        "output_cost_per_1k": 0.0,
        "capabilities": ["text", "json", "code"],
        "context_window": 32768,
        "baseline_latency_ms": 280.0,
        "enabled": True,
    },
    {
        "id": str(uuid.uuid4()),
        "provider": "ollama",
        "model_name": "qwen2.5:latest",
        "display_name": "Qwen 2.5 (latest tag)",
        "input_cost_per_1k": 0.0,
        "output_cost_per_1k": 0.0,
        "capabilities": ["text", "json", "code"],
        "context_window": 32768,
        "baseline_latency_ms": 280.0,
        "enabled": True,
    },
]


def upgrade() -> None:
    """Create model_registry table and seed default model catalog."""
    now = _now()

    op.create_table(
        "model_registry",

        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),

        # Pricing
        sa.Column("input_cost_per_1k", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("output_cost_per_1k", sa.Float(), nullable=False, server_default="0.0"),

        # Capabilities stored as JSONB (list of strings)
        sa.Column("capabilities", JSONB, nullable=False, server_default="[]"),

        sa.Column("context_window", sa.Integer(), nullable=False, server_default="8192"),
        sa.Column("baseline_latency_ms", sa.Float(), nullable=False, server_default="500.0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),

        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),

        # Constraints
        sa.UniqueConstraint("provider", "model_name", name="uq_model_registry_provider_model"),
    )

    # Indexes
    op.create_index("ix_model_registry_provider", "model_registry", ["provider"])
    op.create_index("ix_model_registry_enabled", "model_registry", ["enabled"])

    # Seed default catalog
    import json
    table = sa.table(
        "model_registry",
        sa.column("id", sa.String),
        sa.column("provider", sa.String),
        sa.column("model_name", sa.String),
        sa.column("display_name", sa.String),
        sa.column("input_cost_per_1k", sa.Float),
        sa.column("output_cost_per_1k", sa.Float),
        sa.column("capabilities", sa.String),  # JSONB serialized as string for op.bulk_insert
        sa.column("context_window", sa.Integer),
        sa.column("baseline_latency_ms", sa.Float),
        sa.column("enabled", sa.Boolean),
        sa.column("added_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )

    rows = []
    for m in _SEED_MODELS:
        rows.append(
            {
                "id": m["id"],
                "provider": m["provider"],
                "model_name": m["model_name"],
                "display_name": m["display_name"],
                "input_cost_per_1k": m["input_cost_per_1k"],
                "output_cost_per_1k": m["output_cost_per_1k"],
                "capabilities": json.dumps(m["capabilities"]),
                "context_window": m["context_window"],
                "baseline_latency_ms": m["baseline_latency_ms"],
                "enabled": m["enabled"],
                "added_at": now,
                "updated_at": now,
            }
        )

    op.bulk_insert(table, rows)


def downgrade() -> None:
    """Drop model_registry table."""
    op.drop_index("ix_model_registry_enabled", table_name="model_registry")
    op.drop_index("ix_model_registry_provider", table_name="model_registry")
    op.drop_table("model_registry")
