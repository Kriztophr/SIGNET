from fastapi import APIRouter

from app.platform.settings.config import get_settings

router = APIRouter(tags=["platform"])


@router.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }
