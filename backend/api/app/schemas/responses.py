from pydantic import BaseModel


class SpeechToTextResponse(BaseModel):
    transcript: str
    confidence: float | None = None
    status: str


class TextToKslResponse(BaseModel):
    gloss: list[str]
    lesson_asset_id: str | None = None
    status: str


class SignToTextResponse(BaseModel):
    label: str | None = None
    confidence: float | None = None
    text: str | None = None
    status: str


class PhotoExplainResponse(BaseModel):
    object_name: str | None = None
    explanation: str
    suggested_sign: str | None = None
    status: str
