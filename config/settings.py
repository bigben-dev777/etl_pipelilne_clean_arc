"""
Configuration management for the ETL pipeline.
Uses pydantic-settings for environment-based configuration.
"""

import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Project paths
    PROJECT_ROOT: Path = Path(__file__).parent.parent
    DATA_DIR: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent / "data"
    )
    RAW_DATA_DIR: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent / "data" / "raw"
    )
    PROCESSED_DIR: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent / "data" / "processed"
    )

    # Database settings
    DATABASE_URL: str = Field(default="sqlite:///./data/processed/leads.db")
    DB_ECHO: bool = Field(default=False)

    # LLM Provider settings
    LLM_PROVIDER: str = Field(default="openai", description="openai or anthropic")
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None)
    GEMINI_API_KEY: Optional[str] = Field(default=None)

    # Model selection
    LLM_MODEL_CLASSIFICATION: str = Field(default="gpt-4o-mini")
    LLM_MODEL_RESOLUTION: str = Field(default="gpt-4o")
    LLM_TEMPERATURE: float = Field(default=0.0)
    LLM_MAX_TOKENS: int = Field(default=4000)

    # Cost control
    LLM_MAX_CALLS_PER_RUN: int = Field(default=100)
    LLM_ENABLE_CACHING: bool = Field(default=True)
    LLM_CACHE_TTL_HOURS: int = Field(default=24)

    # AI feature toggles
    AI_ENABLE_SCHEMA_INFERENCE: bool = Field(default=True)
    AI_ENABLE_FACILITY_CLASSIFICATION: bool = Field(default=True)
    AI_ENABLE_ENTITY_RESOLUTION: bool = Field(default=True)
    AI_FALLBACK_TO_RULES: bool = Field(default=True)

    # Processing settings
    BATCH_SIZE: int = Field(default=100)
    CHUNK_SIZE: int = Field(default=1000)
    MAX_WORKERS: int = Field(default=4)

    # Data quality thresholds
    MIN_DATA_QUALITY_SCORE: int = Field(default=30)
    DUPLICATE_PHONE_THRESHOLD: float = Field(default=1.0)
    DUPLICATE_FUZZY_THRESHOLD: float = Field(default=0.85)
    DUPLICATE_AI_THRESHOLD: float = Field(default=0.70)

    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FORMAT: str = Field(default="structured")

    @property
    def db_path(self) -> Path:
        """Get database path from URL."""
        if self.DATABASE_URL.startswith("sqlite:///"):
            return Path(self.DATABASE_URL.replace("sqlite:///", ""))
        return Path("./leads.db")

    @property
    def has_llm_credentials(self) -> bool:
        """Check if LLM credentials are configured."""
        if self.LLM_PROVIDER == "openai":
            return self.OPENAI_API_KEY is not None and len(self.OPENAI_API_KEY) > 0
        elif self.LLM_PROVIDER == "anthropic":
            return (
                self.ANTHROPIC_API_KEY is not None and len(self.ANTHROPIC_API_KEY) > 0
            )
        elif self.LLM_PROVIDER == "gemini":
            return self.GEMINI_API_KEY is not None and len(self.GEMINI_API_KEY) > 0
        return False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings
