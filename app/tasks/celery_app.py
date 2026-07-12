from celery import Celery

from app.platform.settings.config import get_settings

settings = get_settings()

celery_app = Celery(
    "icm-platform",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
)


@celery_app.task(name="platform.ping")
def ping() -> str:
    """Liveness task used by worker healthchecks and smoke tests."""
    return "pong"


# The worker command loads only this module, so every task module must be
# imported here to register its tasks — a task missing from this list is
# silently dropped as "unregistered" on the worker. (Bottom of file: these
# modules import celery_app from here.)
from app.tasks import agent_tasks, judge_tasks  # noqa: E402,F401
