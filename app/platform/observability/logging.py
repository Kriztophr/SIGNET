import logging

import structlog

from app.platform.settings.config import get_settings


def configure_logging() -> None:
    """Structured logging to stdout: JSON in production, readable console in dev."""
    settings = get_settings()
    renderer: structlog.typing.Processor
    if settings.is_production:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.INFO if settings.is_production else logging.DEBUG
        ),
        cache_logger_on_first_use=True,
    )
