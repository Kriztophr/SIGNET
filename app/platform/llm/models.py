import uuid

from sqlalchemy import Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db.base import Base, TenantScopedMixin, TimestampedMixin, UuidPkMixin


class LLMUsage(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    """One LLM call's token spend — the ledger the monthly budget cap reads.

    Rows are append-only evidence: which model, for what purpose (executor /
    judge), against which run/stage, and what it cost. The budget check sums
    cost_usd for the calendar month and fails closed at the configured cap.
    """

    __tablename__ = "llm_usage"

    model: Mapped[str] = mapped_column(String(100), nullable=False)
    purpose: Mapped[str] = mapped_column(String(30), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    workflow_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    stage_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    eval_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
