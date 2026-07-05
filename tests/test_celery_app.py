from app.platform.settings.config import get_settings
from app.tasks.celery_app import celery_app, ping


def test_celery_broker_comes_from_settings() -> None:
    assert celery_app.conf.broker_url == get_settings().redis_url


def test_celery_uses_json_serialization() -> None:
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.accept_content == ["json"]


def test_ping_task_is_registered_and_executes() -> None:
    assert "platform.ping" in celery_app.tasks
    result = ping.apply()
    assert result.get() == "pong"
