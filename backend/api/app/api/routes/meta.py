from fastapi import APIRouter

from ...core.config import settings

router = APIRouter(tags=["meta"])


def _api_index() -> dict[str, object]:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "api_prefix": settings.api_v1_prefix,
        "docs": "/docs",
        "health": f"{settings.api_v1_prefix}/health",
        "status": "ok",
        "available_endpoints": [
            "GET /api/v1",
            "GET /api/v1/health",
            "POST /api/v1/text-to-ksl",
            "GET /api/v1/lesson-assets/{asset_id}/stickman-video",
            "POST /api/v1/text-to-speech",
            "POST /api/v1/speech-to-text",
            "POST /api/v1/sign-to-text",
            "POST /api/v1/sign-to-text-upload",
            "POST /api/v1/sign-sequence-to-text",
            "POST /api/v1/sign-sequence-to-text-upload",
            "POST /api/v1/photo-explain",
            "POST /api/v1/photo-explain-upload",
        ],
    }


@router.get("/")
def api_index_with_slash() -> dict[str, object]:
    return _api_index()
