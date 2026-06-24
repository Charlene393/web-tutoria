from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Web Tutoria API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    sign_recognizer_artifact_path: str | None = None
    sign_recognizer_manifest_path: str | None = None
    sign_recognizer_label_set_path: str | None = None
    sign_recognizer_min_samples_per_label: int = 5
    sign_recognizer_target_frames: int = 24
    sign_recognizer_default_top_k: int = 3
    sign_video_target_fps: float = 8.0
    sign_video_max_frames: int = 48
    sign_video_model_complexity: int = 1
    sign_video_min_detection_confidence: float = 0.5
    sign_video_min_tracking_confidence: float = 0.5
    sign_video_mediapipe_model_path: str | None = None
    faster_whisper_model_size: str = "small"
    faster_whisper_device: str = "cpu"
    faster_whisper_compute_type: str = "int8"
    faster_whisper_language: str | None = "en"
    faster_whisper_beam_size: int = 5
    faster_whisper_vad_filter: bool = True
    kokoro_voice: str = "af_heart"
    kokoro_lang_code: str = "a"
    kokoro_model_id: str = "Kokoro-82M"
    kokoro_sample_rate: int = 24000
    kokoro_speed: float = 1.0
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:4173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:4173",
        ]
    )
    allowed_origin_regex: str = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
