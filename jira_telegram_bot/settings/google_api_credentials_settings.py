"""Google API credentials settings."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class GoogleApiCredentialsSettings(BaseSettings):
    """Settings for Google API service account credentials.
    
    This settings class is shared across all Google API services
    (Sheets, Docs, Drive, etc.) as they use the same service account.
    """
    
    token_path: str = Field(
        description="Path to the Google API service account credentials JSON file",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="google_api_",
        extra="ignore",
    )
