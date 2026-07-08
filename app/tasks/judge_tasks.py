"""Celery execution of LLM-judge scoring (spec §28.8).

Same seam shape as agent_tasks: the eval-run service calls
:func:`dispatch_judge_scoring`, which by default enqueues the Celery task with
a short countdown so the API request's transaction commits before the worker
reads the row. Tests replace the dispatcher with a synchronous fake. The judge
is advisory, so a broken broker is just a logged warning — human scoring is
never affected.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

_ENQUEUE_COUNTDOWN_SECONDS = 2


@celery_app.task(
    name="evals.judge_score",
    bind=True,
    max_retries=3,
    default_retry_delay=5,
)
def judge_score_task(self, eval_run_id: str) -> None:
    from app.evals.services.judge import JudgeEvalService
    from app.platform.db.session import get_sessionmaker
    from app.platform.storage.service import get_storage

    with get_sessionmaker()() as session:
        try:
            JudgeEvalService(session, get_storage()).score_run(uuid.UUID(eval_run_id))
            session.commit()
        except LookupError as exc:
            # The enqueueing transaction may not have committed yet — retry.
            session.rollback()
            raise self.retry(exc=exc)


def _enqueue(eval_run_id: uuid.UUID) -> None:
    judge_score_task.apply_async(
        args=[str(eval_run_id)],
        countdown=_ENQUEUE_COUNTDOWN_SECONDS,
        retry=False,  # a dead broker should fail fast, not hang the API request
    )


# The active dispatcher. Tests (or synchronous deployments) may replace it.
_dispatcher: Callable[[uuid.UUID], None] = _enqueue


def set_judge_dispatcher(dispatcher: Callable[[uuid.UUID], None] | None) -> None:
    global _dispatcher
    _dispatcher = dispatcher if dispatcher is not None else _enqueue


def dispatch_judge_scoring(eval_run_id: uuid.UUID) -> None:
    """Best-effort dispatch: on failure the run simply gets no judge score."""
    try:
        _dispatcher(eval_run_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "judge_dispatch_failed",
            eval_run_id=str(eval_run_id),
            error=str(exc),
        )
