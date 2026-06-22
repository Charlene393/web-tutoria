from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ...schemas.requests import PhotoExplainRequest
from ...schemas.requests import PhotoExplainUploadRequest
from ...schemas.responses import PhotoExplainResponse
from ...services.photo_explain_service import explain_photo
from ...services.photo_explain_service import explain_uploaded_photo

router = APIRouter(tags=["photo-explain"])


@router.post("/photo-explain", response_model=PhotoExplainResponse)
def photo_explain(request: PhotoExplainRequest) -> PhotoExplainResponse:
    try:
        return explain_photo(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/photo-explain-upload", response_model=PhotoExplainResponse)
async def photo_explain_upload(
    image: UploadFile = File(...),
    object_name: str | None = Form(None),
    prompt: str | None = Form(None),
    include_ksl: bool = Form(True),
    include_speech: bool = Form(False),
    voice_id: str | None = Form(None),
    output_format: str | None = Form(None),
    session_id: str | None = Form(None),
) -> PhotoExplainResponse:
    request = PhotoExplainUploadRequest(
        filename=image.filename,
        content_type=image.content_type,
        image_bytes=await image.read(),
        object_name=object_name,
        prompt=prompt,
        include_ksl=include_ksl,
        include_speech=include_speech,
        voice_id=voice_id,
        output_format=output_format,
        session_id=session_id,
    )
    try:
        return explain_uploaded_photo(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
