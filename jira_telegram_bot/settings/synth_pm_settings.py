"""Settings for SynthPM feature."""
from __future__ import annotations

from typing import List
from typing import Optional
from typing import TYPE_CHECKING

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

if TYPE_CHECKING:
    from jira_telegram_bot.entities.synth_pm.sync_filter_criteria import (
        SynthPMSyncFilterCriteria,
    )


class SynthPMSettings(BaseSettings):
    """Settings for SynthPM feature integration."""

    # Google Sheets Configuration (fallback to main settings if not specified)
    google_sheets_token_path: str = Field(
        default="pm-684f8662ca98.json",
        description="Path to Google Sheets API token JSON file (defaults to main token)",
    )
    google_sheets_id: str = Field(
        default="1TCvcE_IsP6jpHp3pVfjND9Kys8rfsB5fp2Sx0LILwm4",
        description="Google Sheet ID containing Features (defaults to main sheet)",
    )
    # pm_worksheet_name: str = Field(
    #     default="Features",
    #     description="Name of the worksheet containing features"
    # )
    developer_board_worksheet_name: str = Field(
        default="Developer Board",
        description="Name of the worksheet containing Developer Board",
    )
    release_notes_worksheet_name: str = Field(
        default="Release Notes",
        description="Name of the worksheet containing Release Notes",
    )

    # Jira Configuration (business rule - configured in code)
    developer_board_project_key: str = Field(
        default="PM Board",
        description="Jira project key for creating tasks",
    )
    pm_project_key: str = Field(
        description="Project key for linked tasks",
    )

    # Telegram Configuration (environment-specific)
    telegram_channel_id: str = Field(
        description="Telegram channel ID for posting updates",
    )
    telegram_group_id: str = Field(
        description="Telegram group ID connected to the channel",
    )
    telegram_bot_token: str = Field(
        description="Dedicated Telegram bot token for SynthPM notifications",
    )

    # Feature Configuration (business rule - configured in code)
    status_trigger_value: str = Field(
        default="۲",
        description="Status value that triggers Telegram posting",
    )
    sync_interval_minutes: int = Field(
        default=5,
        description="Interval in minutes for syncing changes",
    )

    # Filtering Configuration (optional for targeted synchronization)
    default_filter_sprints: Optional[List[str]] = Field(
        default=None,
        description="Default list of sprints to filter by (comma-separated env var)",
    )
    default_filter_releases: Optional[List[str]] = Field(
        default=None,
        description="Default list of releases to filter by (comma-separated env var)",
    )
    default_filter_versions: Optional[List[str]] = Field(
        default=None,
        description="Default list of versions to filter by (comma-separated env var)",
    )
    filter_include_empty_sprint: bool = Field(
        default=True,
        description="Whether to include features with empty sprint when filtering",
    )
    filter_include_empty_release: bool = Field(
        default=True,
        description="Whether to include features with empty release when filtering",
    )
    enable_default_filtering: bool = Field(
        default=False,
        description="Whether to enable default filtering for all sync operations",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="synth_pm_",
        extra="ignore",
    )

    def get_default_filter_criteria(self) -> Optional["SynthPMSyncFilterCriteria"]:
        """Get default filter criteria from settings.

        Returns:
            Filter criteria instance if filtering is enabled, None otherwise
        """
        if not self.enable_default_filtering:
            return None

        # Import here to avoid circular imports
        from jira_telegram_bot.entities.synth_pm.sync_filter_criteria import (
            SynthPMSyncFilterCriteria,
        )

        return SynthPMSyncFilterCriteria.create_combined_filter(
            sprints=self.default_filter_sprints,
            releases=self.default_filter_releases,
            versions=self.default_filter_versions,
            include_empty_sprint=self.filter_include_empty_sprint,
            include_empty_release=self.filter_include_empty_release,
        )
