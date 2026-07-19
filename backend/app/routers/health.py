from fastapi import APIRouter, Depends

from app.config import Settings, get_settings


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/version")
def version(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {
        "app_version": settings.app_version,
        "git_commit": settings.git_commit,
        "environment": settings.app_env,
        "build_timestamp": settings.build_timestamp,
    }
