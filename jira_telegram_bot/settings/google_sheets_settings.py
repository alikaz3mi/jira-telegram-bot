from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from jira_telegram_bot.settings.google_api_credentials_settings import (
    GoogleApiCredentialsSettings,
)


class GoogleSheetsConnectionSettings(BaseSettings):
    """Google Sheets specific connection settings.
    
    Note: Credentials are managed separately via GoogleApiCredentialsSettings.
    """
    
    sheet_id: str = Field(
        description="Google Sheet ID to use for task creation",
    )
    worksheet_name: str = Field(
        default="Assignments",
        description="Name of the worksheet containing task assignments",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="google_sheets_",
        extra="ignore",
    )
