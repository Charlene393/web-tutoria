from __future__ import annotations

from pydantic import BaseModel, Field


class SpeechToTextResponse(BaseModel):
    transcript: str
    confidence: float | None = None
    provider: str | None = None
    model_id: str | None = None
    detected_language: str | None = None
    text_to_ksl: TextToKslResponse | None = None
    status: str


class TextToSpeechResponse(BaseModel):
    text: str
    audio_base64: str
    audio_size_bytes: int
    content_type: str
    file_extension: str
    provider: str | None = None
    model_id: str | None = None
    voice_id: str | None = None
    output_format: str | None = None
    text_to_ksl: TextToKslResponse | None = None
    status: str


class LessonAsset(BaseModel):
    asset_id: str
    label: str
    sample_count: int
    source: str
    landmark_path: str | None = None
    stickman_video_path: str | None = None
    batch: str | None = None
    signer_id: str | None = None
    frame_count: int | None = None
    sample_flags: list[str] = Field(default_factory=list)
    quality_score: float | None = None
    selected_from_flagged_sample: bool | None = None


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
    catalog_backed: bool | None = None
    catalog_name: str | None = None
    catalog_generated_at: str | None = None
    status: str


class SignMatchCandidate(BaseModel):
    label: str
    confidence: float
    landmark_path: str | None = None
    lesson_asset_id: str | None = None


class SignToTextResponse(BaseModel):
    label: str | None = None
    confidence: float | None = None
    text: str | None = None
    provider: str | None = None
    model_id: str | None = None
    source_landmark_path: str | None = None
    matched_landmark_path: str | None = None
    lesson_asset_id: str | None = None
    dataset_backed: bool = False
    top_matches: list[SignMatchCandidate] = Field(default_factory=list)
    status: str


class PhotoExplainResponse(BaseModel):
    object_name: str | None = None
    explanation: str
    suggested_sign: str | None = None
    status: str
