from pydantic import BaseModel


class SpeechToTextResponse(BaseModel):
    transcript: str
    confidence: float | None = None
    status: str


class LessonAsset(BaseModel):
    asset_id: str
    label: str
    sample_count: int
    source: str
    landmark_path: str | None = None
    stickman_video_path: str | None = None


class TextToKslResponse(BaseModel):
    original_text: str
    normalized_text: str
    gloss: list[str]
    matched_terms: list[str]
    unmatched_terms: list[str]
    supported: bool
    dataset_backed: bool
    dataset_label_counts: dict[str, int]
    lesson_assets: list[LessonAsset]
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
