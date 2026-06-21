from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Web Tutoria API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
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
        ]
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
