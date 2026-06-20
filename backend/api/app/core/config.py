from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Web Tutoria API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    elevenlabs_api_key: str | None = None
    elevenlabs_tts_voice_id: str | None = None
    elevenlabs_tts_model_id: str = "eleven_flash_v2_5"
    elevenlabs_stt_model_id: str = "scribe_v2"
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
