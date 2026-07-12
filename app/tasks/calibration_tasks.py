"""Celery execution of judge-calibration runs (roadmap stage 4b).

Same seam shape as agent_tasks/judge_tasks: the calibration-run service calls
:func:`dispatch_calibration_run`, which by default enqueues the Celery task
with a short countdown so the API request's transaction commits before the
worker reads the row. Tests replace the dispatcher with a synchronous fake.
A broken broker leaves the run pending — it can be re-dispatched; production
judging and human scoring are never affected.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

_ENQUEUE_COUNTDOWN_SECONDS = 2


@celery_app.task(
    name="evals.calibration_run",
    bind=True,
    max_retries=3,
    default_retry_delay=5,
)
def calibration_run_task(self, calibration_run_id: str) -> None:
    from app.evals.calibration.service import CalibrationRunService
    from app.platform.db.session import get_sessionmaker
    from app.platform.storage.service import get_storage

    with get_sessionmaker()() as session:
        try:
            CalibrationRunService(session, get_storage()).execute(uuid.UUID(calibration_run_id))
            session.commit()
        except LookupError as exc:
            # The enqueueing transaction may not have committed yet — retry.
            session.rollback()
            raise self.retry(exc=exc) from exc


def _enqueue(calibration_run_id: uuid.UUID) -> None:
    calibration_run_task.apply_async(
        args=[str(calibration_run_id)],
        countdown=_ENQUEUE_COUNTDOWN_SECONDS,
        retry=False,  # a dead broker should fail fast, not hang the API request
    )


# The active dispatcher. Tests (or synchronous deployments) may replace it.
_dispatcher: Callable[[uuid.UUID], None] = _enqueue


def set_calibration_dispatcher(dispatcher: Callable[[uuid.UUID], None] | None) -> None:
    global _dispatcher
    _dispatcher = dispatcher if dispatcher is not None else _enqueue


def dispatch_calibration_run(calibration_run_id: uuid.UUID) -> None:
    """Best-effort dispatch: on failure the run stays pending for re-dispatch."""
    try:
        _dispatcher(calibration_run_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "calibration_dispatch_failed",
            calibration_run_id=str(calibration_run_id),
            error=str(exc),
        )
