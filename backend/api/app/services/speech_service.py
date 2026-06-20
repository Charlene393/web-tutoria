from ..schemas.requests import SpeechToTextRequest
from ..schemas.responses import SpeechToTextResponse


def transcribe_speech(_: SpeechToTextRequest) -> SpeechToTextResponse:
    return SpeechToTextResponse(
        transcript="Speech pipeline not connected yet.",
        confidence=None,
        status="stub",
    )
