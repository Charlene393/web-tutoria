from fastapi import APIRouter
from fastapi import HTTPException

from ...schemas.requests import SignToTextRequest
from ...schemas.responses import SignToTextResponse
from ...services.sign_to_text_service import recognize_sign

router = APIRouter(tags=["sign-to-text"])


@router.post("/sign-to-text", response_model=SignToTextResponse)
def sign_to_text(request: SignToTextRequest) -> SignToTextResponse:
    try:
        return recognize_sign(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
