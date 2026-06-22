from fastapi import APIRouter
from fastapi import File
from fastapi import Form
from fastapi import HTTPException
from fastapi import UploadFile

from ...schemas.requests import SignToTextRequest
from ...schemas.requests import SignUploadToTextRequest
from ...schemas.responses import SignToTextResponse
from ...services.sign_to_text_service import recognize_sign
from ...services.sign_to_text_service import recognize_uploaded_sign

router = APIRouter(tags=["sign-to-text"])


@router.post("/sign-to-text", response_model=SignToTextResponse)
def sign_to_text(request: SignToTextRequest) -> SignToTextResponse:
    try:
        return recognize_sign(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/sign-to-text-upload", response_model=SignToTextResponse)
async def sign_to_text_upload(
    sign_file: UploadFile = File(...),
    top_k: int = Form(3),
    include_speech: bool = Form(False),
    voice_id: str | None = Form(None),
    output_format: str | None = Form(None),
    session_id: str | None = Form(None),
) -> SignToTextResponse:
    request = SignUploadToTextRequest(
        filename=sign_file.filename,
        content_type=sign_file.content_type,
        file_bytes=await sign_file.read(),
        top_k=top_k,
        include_speech=include_speech,
        voice_id=voice_id,
        output_format=output_format,
        session_id=session_id,
    )

    try:
        return recognize_uploaded_sign(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
