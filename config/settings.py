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


TAEGET_COLUMN_DESCRIPTION = {
    "company": (
        "Facility or business legal operating name. "
        "Data type: VARCHAR. Required. Trimmed string, no leading/trailing spaces. "
        "Should not contain license status text (e.g., 'Licensed')."
    ),
    "facility_type": (
        "Categorical value describing facility classification "
        "(e.g., Center, Family Child Care, Group Home). "
        "Data type: VARCHAR. Controlled vocabulary preferred."
    ),
    "address1": (
        "Primary street address line. "
        "Data type: VARCHAR. Required. "
        "Should contain street number and street name only."
    ),
    "address2": (
        "Secondary address information (suite, unit, apartment, building). "
        "Data type: VARCHAR. Nullable."
    ),
    "city": (
        "City name derived from address. "
        "Data type: VARCHAR. Required. "
        "Should be properly capitalized and not contain state or ZIP."
    ),
    "state": (
        "Two-letter USPS state abbreviation (e.g., 'CA', 'TX'). "
        "Data type: VARCHAR(2). Required. Must be uppercase."
    ),
    "zip": (
        "5-digit or 9-digit ZIP code. "
        "Data type: VARCHAR. Required. "
        "Must match regex: ^\\d{5}(-\\d{4})?$"
    ),
    "county": (
        "County name without suffix normalization (e.g., 'Orange', not 'Orange County'). "
        "Data type: VARCHAR. Nullable."
    ),
    "phone": (
        "Primary contact phone number. "
        "Data type: VARCHAR. "
        "Normalized to digits only or standard format (e.g., (###) ###-####)."
    ),
    "phone2": (
        "Secondary phone number if available. "
        "Data type: VARCHAR. Nullable. Same normalization rules as phone."
    ),
    "email": (
        "Primary contact email address. "
        "Data type: VARCHAR. Nullable. "
        "Must match basic email regex validation."
    ),
    "website_address": (
        "Facility website URL. "
        "Data type: VARCHAR. Nullable. "
        "Should include scheme (http:// or https://)."
    ),
    "first_name": (
        "Primary contact person's first name. "
        "Data type: VARCHAR. Nullable. "
        "Should not include titles (e.g., Mr., Dr.)."
    ),
    "last_name": (
        "Primary contact person's last name. " "Data type: VARCHAR. Nullable."
    ),
    "capacity": (
        "Maximum number of children allowed by license. "
        "Data type: NUMERIC. Must be >= 0. "
        "Represents total capacity, not per classroom."
    ),
    "min_age": (
        "Minimum age served (in months unless standardized differently). "
        "Data type: NUMERIC. Must be >= 0 and <= max_age."
    ),
    "max_age": (
        "Maximum age served (in months unless standardized differently). "
        "Data type: NUMERIC. Must be >= min_age."
    ),
    "ages_served": (
        "Free-text description of age range (e.g., '6 weeks to 5 years'). "
        "Data type: VARCHAR. "
        "Used when structured min/max not available."
    ),
    "license_status": (
        "Current license status (e.g., Licensed, Probationary, Revoked, Closed). "
        "Data type: VARCHAR. "
        "Should be normalized to controlled vocabulary."
    ),
    "license_number": (
        "Official state-issued license or credential number. "
        "Data type: VARCHAR. Required if license_status indicates active license."
    ),
    "license_type": (
        "Type/category of license issued by regulator. "
        "Data type: VARCHAR. "
        "Should align with facility_type but may differ."
    ),
}
