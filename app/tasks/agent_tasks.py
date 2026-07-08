"""Celery execution of automated stages (spec §28.7).

Dispatch is a seam: the coordinator calls :func:`dispatch_agent_execution`,
which by default enqueues the Celery task with a short countdown (so the API
request's transaction commits before the worker reads the row). Tests replace
the dispatcher with a synchronous fake; a broken broker degrades to manual
execution with the reason recorded on the stage run — an infrastructure
failure must never take the run down with it.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

_ENQUEUE_COUNTDOWN_SECONDS = 2


@celery_app.task(
    name="workflow.execute_stage",
    bind=True,
    max_retries=3,
    default_retry_delay=5,
)
def execute_stage_task(self, stage_run_id: str) -> None:
    from app.platform.db.session import get_sessionmaker
    from app.platform.storage.service import get_storage
    from app.workflow.services.agent_execution import AgentStageExecutor

    with get_sessionmaker()() as session:
        try:
            AgentStageExecutor(session, get_storage()).execute_stage(uuid.UUID(stage_run_id))
            session.commit()
        except LookupError as exc:
            # The enqueueing transaction may not have committed yet — retry.
            session.rollback()
            raise self.retry(exc=exc)


def _enqueue(stage_run_id: uuid.UUID) -> None:
    execute_stage_task.apply_async(
        args=[str(stage_run_id)],
        countdown=_ENQUEUE_COUNTDOWN_SECONDS,
        retry=False,  # a dead broker should fail fast, not hang the API request
    )


# The active dispatcher. Tests (or synchronous deployments) may replace it.
_dispatcher: Callable[[uuid.UUID], None] = _enqueue


def set_agent_dispatcher(dispatcher: Callable[[uuid.UUID], None] | None) -> None:
    global _dispatcher
    _dispatcher = dispatcher if dispatcher is not None else _enqueue


def dispatch_agent_execution(stage_run_id: uuid.UUID) -> None:
    """Best-effort dispatch: on failure the stage simply stays manual."""
    try:
        _dispatcher(stage_run_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "agent_dispatch_failed",
            stage_run_id=str(stage_run_id),
            error=str(exc),
        )
