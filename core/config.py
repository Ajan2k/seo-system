# core/config.py
"""
Centralized Application Configuration
Loads and validates all environment variables with type safety.
"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """
    Application Settings – loaded from .env or environment.
    All fields are type-validated by Pydantic.
    """

    # ── Application ─────────────────────────────────────────────────────────
    APP_NAME: str = Field(default="AI Blog Automation", description="Application display name")
    APP_VERSION: str = Field(default="2.0.0")
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="production")  # production | development | testing
    SECRET_KEY: str = Field(default="c3VwZXJzZWNyZXQtand0LWtleS1jaGFuZ2UtbWU=")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 24 * 7) # 7 days

    # ── Server ───────────────────────────────────────────────────────────────
    HOST: str = Field(default="127.0.0.1")
    PORT: int = Field(default=8001)

    # ── Database ─────────────────────────────────────────────────────────────
    # PostgreSQL is configured via DATABASE_URL env var in models.py

    # ── AI / Groq ────────────────────────────────────────────────────────────
    GROQ_API_KEY: str = Field(default="")
    GROQ_MODEL: str = Field(default="llama-3.3-70b-versatile")
    GROQ_MAX_TOKENS: int = Field(default=7000)
    GROQ_TEMPERATURE: float = Field(default=0.1)
    GROQ_TIMEOUT: float = Field(default=120.0)

    # ── Image APIs ───────────────────────────────────────────────────────────
    PEXELS_API_KEY: str = Field(default="")
    SERPAPI_API_KEY: str = Field(default="")
    HF_API_KEY: str = Field(default="", description="HuggingFace API token for FLUX/SDXL image generation (free at huggingface.co/settings/tokens)")

    # ── SEO Defaults ──────────────────────────────────────────────────────────
    SEO_TARGET_SCORE: int = Field(default=80)
    SEO_META_MAX_LENGTH: int = Field(default=143)
    SEO_META_MIN_LENGTH: int = Field(default=120)
    SEO_TITLE_MAX_LENGTH: int = Field(default=60)
    SEO_WORD_COUNT_TARGET: int = Field(default=1600)

    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

    # ── Logging ──────────────────────────────────────────────────────────────
    LOG_LEVEL: str = Field(default="INFO")       # DEBUG | INFO | WARNING | ERROR | CRITICAL
    LOG_DIR: str = Field(default="logs")
    LOG_RETENTION_DAYS: int = Field(default=30)
    LOG_MAX_FILE_SIZE_MB: int = Field(default=10)

    # ── CORS ─────────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = Field(default="*")       # Comma-separated list or "*"

    # ── Brand ────────────────────────────────────────────────────────────────
    DEFAULT_BRAND_NAME: str = Field(default="Infinitetechai")
    DEFAULT_INDUSTRIES: str = Field(default="healthcare,education,e-commerce,real estate")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    # ── Computed helpers ──────────────────────────────────────────────────────

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def default_industries_list(self) -> list[str]:
        return [i.strip() for i in self.DEFAULT_INDUSTRIES.split(",") if i.strip()]

    @property
    def groq_configured(self) -> bool:
        return bool(self.GROQ_API_KEY)

    @property
    def pexels_configured(self) -> bool:
        return bool(self.PEXELS_API_KEY)

    @property
    def hf_configured(self) -> bool:
        return bool(self.HF_API_KEY)

    @property
    def SERP_API_KEY(self) -> str:
        """Alias for SERPAPI_API_KEY – used by web_researcher.py."""
        return self.SERPAPI_API_KEY

    @property
    def serp_configured(self) -> bool:
        return bool(self.SERPAPI_API_KEY)


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance (singleton)."""
    return Settings()


# Module-level convenience reference
settings = get_settings()
