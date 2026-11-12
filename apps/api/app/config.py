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
    DEMO_SHOW_SAMPLE: bool = Field(default=False)

    # Ingestion queries per company (wide-run default 2, configurable per run)
    INGEST_QUERIES_PER_COMPANY: int = Field(default=2)
    TAVILY_FALLBACK_MIN_RESULTS: int = Field(default=3)
    INGEST_QUERY_TEMPLATES: List[str] = Field(
        default=[
            "campus recruiter {company} Mumbai",
            "{company} early careers campus hiring placement report appointment news",
            "university relations talent acquisition {company} India",
            "early careers hiring {company} India",
        ]
    )

    # Data broker blocklist (people-data aggregators rejected before extraction)
    DATA_BROKER_DOMAINS: List[str] = Field(
        default=[
            "rocketreach.co",
            "zoominfo.com",
            "apollo.io",
            "signalhire.com",
            "contactout.com",
            "lusha.com",
            "cognism.com",
            "lead411.com",
            "upconversion.com",
            "swordfish.ai",
            "seamless.ai",
            "kendoemailapp.com",
            "hunter.io",
            "aeroleads.com",
        ]
    )

    # Server settings
    PORT: int = Field(default=8000)
    HOST: str = Field(default="0.0.0.0")
    ENVIRONMENT: str = Field(default="development")
    CORS_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:8000",
            "http://localhost:8001",
            "http://localhost:8080",
            "http://localhost:8081",
            "http://localhost:19000",
            "http://localhost:19006",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
            "http://127.0.0.1:8000",
            "http://127.0.0.1:8001",
            "http://10.0.2.2:3000",
            "http://10.0.2.2:8000",
            "http://10.0.2.2:8001",
            "http://10.0.2.2:8081",
        ]
    )
    CORS_ORIGIN_REGEX: Optional[str] = Field(
        default=r"^https?://(localhost|127\.0\.0\.1|10\.0\.2\.2|192\.168\.\d+\.\d+)(:\d+)?$"
    )

    # Day 4 & Day 5 Role & Demo Settings
    DEMO_LOGIN_ENABLED: bool = Field(default=False)
    DEMO_VERIFY_ENABLED: bool = Field(default=False)
    DEMO_USER_PASSWORD: Optional[str] = Field(default=None)
    OFFICIAL_EMAIL_DENYLIST: List[str] = Field(
        default=[
            "gmail.com",
            "yahoo.com",
            "hotmail.com",
            "outlook.com",
            "tempmail.com",
            "mailinator.com",
            "guerrillamail.com",
        ]
    )

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
