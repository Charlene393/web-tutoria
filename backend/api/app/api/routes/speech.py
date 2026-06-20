from fastapi import APIRouter

from ...schemas.requests import SpeechToTextRequest
from ...schemas.responses import SpeechToTextResponse
from ...services.speech_service import transcribe_speech

router = APIRouter(tags=["speech"])


@router.post("/speech-to-text", response_model=SpeechToTextResponse)
def speech_to_text(request: SpeechToTextRequest) -> SpeechToTextResponse:
    return transcribe_speech(request)
