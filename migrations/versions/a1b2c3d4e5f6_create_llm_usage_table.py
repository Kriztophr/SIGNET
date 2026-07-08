"""create llm_usage table

Revision ID: a1b2c3d4e5f6
Revises: 5d455d6a8efd
Create Date: 2026-07-08 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "5d455d6a8efd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_usage",
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("purpose", sa.String(length=30), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=True),
        sa.Column("stage_run_id", sa.Uuid(), nullable=True),
        sa.Column("eval_run_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_usage")),
    )
    op.create_index(op.f("ix_llm_usage_project_id"), "llm_usage", ["project_id"], unique=False)
    op.create_index(op.f("ix_llm_usage_tenant_id"), "llm_usage", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_llm_usage_tenant_id"), table_name="llm_usage")
    op.drop_index(op.f("ix_llm_usage_project_id"), table_name="llm_usage")
    op.drop_table("llm_usage")
