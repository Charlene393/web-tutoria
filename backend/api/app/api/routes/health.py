from fastapi import APIRouter

from ...schemas.responses import HealthResponse
from ...services.health_service import build_health_response

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> HealthResponse:
    return build_health_response()
