"""create calibration tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-12 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "calibration_examples",
        sa.Column("rubric_version_id", sa.Uuid(), nullable=False),
        sa.Column("content_ref", sa.String(length=500), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("gold_score_json", sa.JSON(), nullable=False),
        sa.Column("gold_pass_fail", sa.Boolean(), nullable=False),
        sa.Column("gold_rationale", sa.Text(), nullable=False),
        sa.Column(
            "split",
            sa.Enum("train", "dev", "test", name="calibrationsplit", native_enum=False, length=10),
            nullable=False,
        ),
        sa.Column("group_key", sa.String(length=200), nullable=False),
        sa.Column("test_set_version", sa.Integer(), nullable=True),
        sa.Column("provenance", sa.String(length=30), nullable=False),
        sa.Column("source_eval_run_id", sa.Uuid(), nullable=True),
        sa.Column("source_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["rubric_version_id"],
            ["rubric_versions.id"],
            name=op.f("fk_calibration_examples_rubric_version_id_rubric_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calibration_examples")),
        sa.UniqueConstraint(
            "tenant_id",
            "source_eval_run_id",
            name=op.f("uq_calibration_examples_tenant_id"),
        ),
    )
    op.create_index(
        op.f("ix_calibration_examples_group_key"),
        "calibration_examples",
        ["group_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_calibration_examples_project_id"),
        "calibration_examples",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_calibration_examples_rubric_version_id"),
        "calibration_examples",
        ["rubric_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_calibration_examples_split"), "calibration_examples", ["split"], unique=False
    )
    op.create_index(
        op.f("ix_calibration_examples_tenant_id"),
        "calibration_examples",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "calibration_runs",
        sa.Column("rubric_version_id", sa.Uuid(), nullable=False),
        sa.Column(
            "split",
            sa.Enum("train", "dev", "test", name="calibrationsplit", native_enum=False, length=10),
            nullable=False,
        ),
        sa.Column("test_set_version", sa.Integer(), nullable=True),
        sa.Column("judge_provider", sa.String(length=30), nullable=False),
        sa.Column("judge_model", sa.String(length=100), nullable=False),
        sa.Column("judge_config_json", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "completed",
                "failed",
                name="calibrationrunstatus",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("results_json", sa.JSON(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("example_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("triggered_by", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["rubric_version_id"],
            ["rubric_versions.id"],
            name=op.f("fk_calibration_runs_rubric_version_id_rubric_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calibration_runs")),
    )
    op.create_index(
        op.f("ix_calibration_runs_judge_model"), "calibration_runs", ["judge_model"], unique=False
    )
    op.create_index(
        op.f("ix_calibration_runs_project_id"), "calibration_runs", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_calibration_runs_rubric_version_id"),
        "calibration_runs",
        ["rubric_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_calibration_runs_tenant_id"), "calibration_runs", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_calibration_runs_tenant_id"), table_name="calibration_runs")
    op.drop_index(op.f("ix_calibration_runs_rubric_version_id"), table_name="calibration_runs")
    op.drop_index(op.f("ix_calibration_runs_project_id"), table_name="calibration_runs")
    op.drop_index(op.f("ix_calibration_runs_judge_model"), table_name="calibration_runs")
    op.drop_table("calibration_runs")
    op.drop_index(op.f("ix_calibration_examples_tenant_id"), table_name="calibration_examples")
    op.drop_index(op.f("ix_calibration_examples_split"), table_name="calibration_examples")
    op.drop_index(
        op.f("ix_calibration_examples_rubric_version_id"), table_name="calibration_examples"
    )
    op.drop_index(op.f("ix_calibration_examples_project_id"), table_name="calibration_examples")
    op.drop_index(op.f("ix_calibration_examples_group_key"), table_name="calibration_examples")
    op.drop_table("calibration_examples")
