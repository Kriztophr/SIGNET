from fastapi import FastAPI

from app.platform.auth.api import router as auth_router
from app.platform.observability.correlation import CorrelationIdMiddleware
from app.platform.observability.health import router as health_router
from app.platform.observability.logging import configure_logging
from app.platform.settings.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        # Interactive API docs are exposed only outside production.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(health_router)
    app.include_router(auth_router)
    return app


app = create_app()
