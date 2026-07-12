"""The prod worker loads only app.tasks.celery_app — every Celery task must be
registered by importing that single module, or dispatches die on the worker as
"Received unregistered task" (found live on 2026-07-12 with evals.judge_score).
"""

from app.tasks.celery_app import celery_app


def test_all_platform_tasks_registered_via_worker_entry_module() -> None:
    registered = set(celery_app.tasks)
    assert "platform.ping" in registered
    assert "workflow.execute_stage" in registered
    assert "evals.judge_score" in registered
    assert "evals.calibration_run" in registered
