"""LLM spend ledger + fail-closed monthly budget cap (charter 2026-07-08).

Every adapter call is recorded as an LLMUsage row; before any call, the
executor asks the ledger whether this month's spend is under the configured
cap. At or over the cap, agent execution refuses to run (BudgetExceededError)
— the stage degrades to manual completion rather than silently overspending.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.platform.errors import DomainValidationError
from app.platform.llm.adapter import LLMResult
from app.platform.llm.models import LLMUsage
from app.platform.settings.config import get_settings

# USD per 1M tokens (input, output). Unknown models bill at the most expensive
# known rate — fail closed on cost, never optimistic.
MODEL_PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
_FALLBACK_PRICE = (10.0, 50.0)


class BudgetExceededError(DomainValidationError):
    pass


def cost_for(model: str, input_tokens: int, output_tokens: int) -> float:
    base = next(
        (price for prefix, price in MODEL_PRICES_PER_MTOK.items() if model.startswith(prefix)),
        _FALLBACK_PRICE,
    )
    return input_tokens / 1_000_000 * base[0] + output_tokens / 1_000_000 * base[1]


class LLMUsageLedger:
    def __init__(self, session: Session) -> None:
        self._session = session

    def month_spend_usd(self) -> float:
        month_start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        total = self._session.execute(
            select(func.coalesce(func.sum(LLMUsage.cost_usd), 0)).where(
                LLMUsage.created_at >= month_start
            )
        ).scalar_one()
        return float(total)

    def ensure_within_budget(self) -> None:
        cap = get_settings().llm_monthly_budget_usd
        spent = self.month_spend_usd()
        if spent >= cap:
            raise BudgetExceededError(
                f"monthly LLM budget exhausted (${spent:.2f} of ${cap:.2f}); "
                "agent execution paused until the cap is raised or the month rolls over"
            )

    def record(
        self,
        tenant_id: uuid.UUID,
        result: LLMResult,
        *,
        purpose: str,
        workflow_run_id: uuid.UUID | None = None,
        stage_run_id: uuid.UUID | None = None,
        eval_run_id: uuid.UUID | None = None,
    ) -> LLMUsage:
        usage = LLMUsage(
            tenant_id=tenant_id,
            model=result.model,
            purpose=purpose,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=cost_for(result.model, result.input_tokens, result.output_tokens),
            workflow_run_id=workflow_run_id,
            stage_run_id=stage_run_id,
            eval_run_id=eval_run_id,
        )
        self._session.add(usage)
        self._session.flush()
        return usage
