"""add llm reports

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def json_object_column(name: str) -> sa.Column[postgresql.JSONB]:
    return sa.Column(
        name,
        postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "llm_reports",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("signal_id", sa.UUID()),
        sa.Column("universe_version_id", sa.UUID()),
        sa.Column("report_type", sa.String(length=32), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="generated", nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("error_message", sa.Text()),
        json_object_column("report_json"),
        json_object_column("request_payload"),
        json_object_column("response_payload"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"]),
        sa.ForeignKeyConstraint(["universe_version_id"], ["asset_universe_versions.id"]),
    )
    op.create_index("ix_llm_reports_signal_id", "llm_reports", ["signal_id"])
    op.create_index("ix_llm_reports_universe_version_id", "llm_reports", ["universe_version_id"])
    op.create_index("ix_llm_reports_report_type", "llm_reports", ["report_type"])
    op.create_index("ix_llm_reports_entity_type", "llm_reports", ["entity_type"])
    op.create_index("ix_llm_reports_entity_id", "llm_reports", ["entity_id"])
    op.create_index("ix_llm_reports_generated_at", "llm_reports", ["generated_at"])


def downgrade() -> None:
    op.drop_table("llm_reports")
