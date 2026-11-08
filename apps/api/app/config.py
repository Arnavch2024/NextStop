import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SUPABASE_URL: str = Field(default="https://placeholder.supabase.co")
    SUPABASE_ANON_KEY: str = Field(default="placeholder-anon-key")
    SUPABASE_SERVICE_KEY: str = Field(default="placeholder-service-key")

    # LLM Settings (Gemini default, provider swappable via env)
    LLM_PROVIDER: str = Field(default="gemini")
    LLM_AGENT_MODEL: str = Field(default="gemini-3.5-flash")
    LLM_FAST_MODEL: str = Field(default="gemini-3.5-flash-lite")

    # Google Gemini settings
    GEMINI_API_KEY: Optional[str] = Field(default=None)
    GOOGLE_API_KEY: Optional[str] = Field(default=None)
    GEMINI_MODEL: str = Field(default="gemini-3.5-flash")

    # Voice transcription settings
    TRANSCRIPTION_PROVIDER: str = Field(default="whisper")
    TRANSCRIPTION_API_KEY: Optional[str] = Field(default=None)
    TRANSCRIPTION_BASE_URL: Optional[str] = Field(default=None)
    TRANSCRIPTION_MODEL: Optional[str] = Field(default=None)
    TRANSCRIPTION_MAX_BYTES: int = Field(default=25 * 1024 * 1024)  # 25MB

    # Day 3 Search Slice settings
    EXA_API_KEY: Optional[str] = Field(default=None)
    TAVILY_API_KEY: Optional[str] = Field(default=None)
    JINA_API_KEY: Optional[str] = Field(default=None)
    WEB_SEARCH_PROVIDER: str = Field(default="exa")
    WEB_FETCH_PROVIDER: Optional[str] = Field(default=None)
    SEARCH_CACHE_TTL_DAYS: int = Field(default=7)
    RESPECT_ROBOTS_TXT: bool = Field(default=True)
    SEED_ENABLED: bool = Field(default=False)

    # Server settings
    PORT: int = Field(default=8000)
    HOST: str = Field(default="0.0.0.0")
    ENVIRONMENT: str = Field(default="development")
    CORS_ORIGINS: List[str] = Field(default=["*"])

    model_config = SettingsConfigDict(
        env_file=(".env", str(Path(__file__).resolve().parent.parent / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def raw_gemini_api_key(self) -> Optional[str]:
        return (
            self.GEMINI_API_KEY
            or self.GOOGLE_API_KEY
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )

    @property
    def effective_gemini_api_key(self) -> str:
        return self.raw_gemini_api_key or "placeholder-gemini-key"


settings = Settings()
