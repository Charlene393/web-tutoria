from fastapi import APIRouter

from ...schemas.requests import SignToTextRequest
from ...schemas.responses import SignToTextResponse
from ...services.sign_to_text_service import recognize_sign

router = APIRouter(tags=["sign-to-text"])


@router.post("/sign-to-text", response_model=SignToTextResponse)
def sign_to_text(request: SignToTextRequest) -> SignToTextResponse:
    return recognize_sign(request)
