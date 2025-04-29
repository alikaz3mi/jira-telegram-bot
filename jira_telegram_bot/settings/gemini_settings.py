from __future__ import annotations

from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class GeminiConnectionSetting(BaseSettings):
    token: str
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="gemini_connection_config_",
        extra="ignore",
    )
