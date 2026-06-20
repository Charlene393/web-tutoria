from fastapi import APIRouter

from ...schemas.requests import TextToKslRequest
from ...schemas.responses import TextToKslResponse
from ...services.text_to_ksl_service import map_text_to_ksl

router = APIRouter(tags=["text-to-ksl"])


@router.post("/text-to-ksl", response_model=TextToKslResponse)
def text_to_ksl(request: TextToKslRequest) -> TextToKslResponse:
    return map_text_to_ksl(request)
