from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ...schemas.requests import SpeechToTextRequest
from ...schemas.responses import SpeechToTextResponse
from ...services.speech_service import transcribe_speech

router = APIRouter(tags=["speech"])


@router.post("/speech-to-text", response_model=SpeechToTextResponse)
async def speech_to_text(
    audio: UploadFile = File(...),
    include_ksl: bool = Form(True),
    session_id: str | None = Form(None),
) -> SpeechToTextResponse:
    audio_bytes = await audio.read()
    request = SpeechToTextRequest(
        filename=audio.filename,
        content_type=audio.content_type,
        audio_bytes=audio_bytes,
        include_ksl=include_ksl,
        session_id=session_id,
    )

    try:
        return transcribe_speech(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
