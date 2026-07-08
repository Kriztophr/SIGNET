"""add scored_by_type to reviewer_scores

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-08

Spec §28.8: an LLM judge records advisory scores as agent-authored
ReviewerScore rows. scored_by_type distinguishes them from human scores so
they never count toward min_reviewers or vote in decisions. Every existing
row was human-submitted, hence the server default.
"""

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reviewer_scores",
        sa.Column(
            "scored_by_type",
            sa.Enum("human", "agent", "system", name="actortype", native_enum=False, length=20),
            server_default="human",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("reviewer_scores", "scored_by_type")
