from pydantic import BaseModel


class SpeechToTextRequest(BaseModel):
    filename: str | None = None
    content_type: str | None = None
    audio_bytes: bytes
    include_ksl: bool = True
    session_id: str | None = None


class TextToSpeechRequest(BaseModel):
    text: str
    voice_id: str | None = None
    output_format: str | None = None
    include_ksl: bool = False
    session_id: str | None = None


class TextToKslRequest(BaseModel):
    text: str


class SignToTextRequest(BaseModel):
    landmark_path: str | None = None
    lesson_asset_id: str | None = None
    video_url: str | None = None
    top_k: int = 3
    include_speech: bool = False
    voice_id: str | None = None
    output_format: str | None = None
    session_id: str | None = None


class SignSequenceItemRequest(BaseModel):
    landmark_path: str | None = None
    lesson_asset_id: str | None = None


class SignSequenceToTextRequest(BaseModel):
    items: list[SignSequenceItemRequest]
    top_k: int = 3
    include_speech: bool = False
    include_ksl: bool = True
    voice_id: str | None = None
    output_format: str | None = None
    session_id: str | None = None


class SignUploadToTextRequest(BaseModel):
    filename: str | None = None
    content_type: str | None = None
    file_bytes: bytes
    top_k: int = 3
    include_speech: bool = False
    voice_id: str | None = None
    output_format: str | None = None
    session_id: str | None = None


class PhotoExplainUploadRequest(BaseModel):
    filename: str | None = None
    content_type: str | None = None
    image_bytes: bytes
    object_name: str | None = None
    prompt: str | None = None
    include_ksl: bool = True
    include_speech: bool = False
    voice_id: str | None = None
    output_format: str | None = None
    session_id: str | None = None


class PhotoExplainRequest(BaseModel):
    object_name: str | None = None
    image_url: str | None = None
    prompt: str | None = None
    include_ksl: bool = True
    include_speech: bool = False
    voice_id: str | None = None
    output_format: str | None = None
    session_id: str | None = None
