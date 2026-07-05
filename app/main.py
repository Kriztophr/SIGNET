from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.environment.api.routes import router as environment_router
from app.evals.api.routes import router as evals_router
from app.governance.api.routes import router as governance_router
from app.platform.auth.api import router as auth_router
from app.platform.errors import (
    DomainValidationError,
    ForbiddenError,
    InvalidStateError,
    NotFoundError,
)
from app.platform.observability.correlation import CorrelationIdMiddleware
from app.platform.observability.health import router as health_router
from app.platform.observability.logging import configure_logging
from app.platform.settings.config import get_settings
from app.workflow.api.routes import router as workflow_router

_ERROR_STATUS = {
    NotFoundError: 404,
    ForbiddenError: 403,
    InvalidStateError: 409,
    DomainValidationError: 422,
}


def _register_error_handlers(app: FastAPI) -> None:
    for error_type, status_code in _ERROR_STATUS.items():

        def handler(
            request: Request, exc: Exception, status_code: int = status_code
        ) -> JSONResponse:
            return JSONResponse(status_code=status_code, content={"detail": str(exc)})

        app.add_exception_handler(error_type, handler)


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
    _register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(workflow_router)
    app.include_router(governance_router)
    app.include_router(evals_router)
    app.include_router(environment_router)
    return app


app = create_app()
