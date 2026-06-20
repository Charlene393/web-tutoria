from pydantic import BaseModel


class SpeechToTextRequest(BaseModel):
    audio_url: str | None = None
    session_id: str | None = None


class TextToKslRequest(BaseModel):
    text: str


class SignToTextRequest(BaseModel):
    landmark_path: str | None = None
    video_url: str | None = None
    session_id: str | None = None


class PhotoExplainRequest(BaseModel):
    image_url: str | None = None
    prompt: str | None = None
