"""Settings for SynthPM feature."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import SettingsConfigDict, BaseSettings


class SynthPMSettings(BaseSettings):
    """Settings for SynthPM feature integration."""
    
    # Google Sheets Configuration (fallback to main settings if not specified)
    google_sheets_token_path: str = Field(
        default="pm-684f8662ca98.json",
        description="Path to Google Sheets API token JSON file (defaults to main token)"
    )
    google_sheets_id: str = Field(
        default="1TCvcE_IsP6jpHp3pVfjND9Kys8rfsB5fp2Sx0LILwm4", 
        description="Google Sheet ID containing Features (defaults to main sheet)"
    )
    # pm_worksheet_name: str = Field(
    #     default="Features",
    #     description="Name of the worksheet containing features"
    # )
    developer_board_worksheet_name: str = Field(
        default="Developer Board",
        description="Name of the worksheet containing Developer Board"
    )
    release_notes_worksheet_name: str = Field(
        default="Release Notes",
        description="Name of the worksheet containing Release Notes"
    )
    
    # Jira Configuration (business rule - configured in code)
    developer_board_project_key: str = Field(
        default="PM Board",
        description="Jira project key for creating tasks"
    )
    pm_project_key: str = Field(
        description="Project key for linked tasks"
    )
    
    # Telegram Configuration (environment-specific)
    telegram_channel_id: str = Field(
        description="Telegram channel ID for posting updates"
    )
    telegram_group_id: str = Field(
        description="Telegram group ID connected to the channel"
    )
    telegram_bot_token: str = Field(
        description="Dedicated Telegram bot token for SynthPM notifications"
    )
    
    # Feature Configuration (business rule - configured in code)
    status_trigger_value: str = Field(
        default="۲",
        description="Status value that triggers Telegram posting"
    )
    sync_interval_minutes: int = Field(
        default=5,
        description="Interval in minutes for syncing changes"
    )
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="synth_pm_",
        extra="ignore",
    )
    
