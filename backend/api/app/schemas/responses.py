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


class ReadinessCheck(BaseModel):
    ready: bool
    required: bool = True
    path: str | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    app_name: str
    app_version: str
    checks: dict[str, ReadinessCheck]


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
    stickman_video_url: str | None = None
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
    source_kind: str | None = None
    source_landmark_path: str | None = None
    source_upload_filename: str | None = None
    matched_landmark_path: str | None = None
    extracted_frame_count: int | None = None
    lesson_asset_id: str | None = None
    dataset_backed: bool = False
    top_matches: list[SignMatchCandidate] = Field(default_factory=list)
    speech: TextToSpeechResponse | None = None
    status: str


class SignSequenceItemResponse(BaseModel):
    index: int
    label: str | None = None
    confidence: float | None = None
    text: str | None = None
    source_kind: str | None = None
    source_landmark_path: str | None = None
    matched_landmark_path: str | None = None
    lesson_asset_id: str | None = None
    top_matches: list[SignMatchCandidate] = Field(default_factory=list)
    status: str


class SignSequenceToTextResponse(BaseModel):
    text: str
    normalized_text: str
    sign_count: int
    items: list[SignSequenceItemResponse] = Field(default_factory=list)
    provider: str | None = None
    model_id: str | None = None
    text_to_ksl: TextToKslResponse | None = None
    speech: TextToSpeechResponse | None = None
    status: str


class PhotoExplainResponse(BaseModel):
    object_name: str | None = None
    normalized_object_name: str | None = None
    explanation: str
    suggested_sign: str | None = None
    provider: str | None = None
    source_kind: str | None = None
    source_image_filename: str | None = None
    text_to_ksl: TextToKslResponse | None = None
    speech: TextToSpeechResponse | None = None
    status: str
