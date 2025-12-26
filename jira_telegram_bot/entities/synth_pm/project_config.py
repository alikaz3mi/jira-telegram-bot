"""Multi-project configuration entities for SynthPM."""
from __future__ import annotations

from typing import Dict
from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class BoardConfig(BaseModel):
    """Configuration for a single board."""

    jira_board_key: Optional[str] = Field(
        default=None,
        description="Jira board key (None if sheet-only)",
    )
    sheet_name: str = Field(
        description="Google Sheet worksheet name",
    )
    data_range: str = Field(
        default="A2:AY",
        description="Data range in the sheet",
    )
    enabled: bool = Field(
        default=True,
        description="Whether this board is enabled",
    )


class TelegramConfig(BaseModel):
    """Telegram configuration for a project."""

    bot_token_env: str = Field(
        description="Environment variable name for bot token",
    )
    channel_id_env: str = Field(
        description="Environment variable name for channel ID",
    )
    group_id_env: str = Field(
        description="Environment variable name for group ID",
    )


class SyncSettings(BaseModel):
    """Synchronization settings for a project."""

    status_trigger_value: str = Field(
        default="۲",
        description="Status value that triggers Telegram posting",
    )
    sync_interval_minutes: int = Field(
        default=5,
        description="Interval in minutes for syncing changes",
    )
    minimum_status_for_task_creation: str = Field(
        default="۵. آماده پیاده سازی فنی",
        description="Minimum status required before creating Jira tasks",
    )
    date_filter_start: Optional[str] = Field(
        default=None,
        description="Filter tasks with dates >= this date (YYYY-MM-DD format). Applies to implementation_start_date and deadline.",
    )
    date_filter_end: Optional[str] = Field(
        default=None,
        description="Filter tasks with dates <= this date (YYYY-MM-DD format). Applies to implementation_start_date and deadline.",
    )
    sprint_filter: Optional[list[str]] = Field(
        default=None,
        description="Filter tasks by sprint names. Only tasks in these sprints will be synced. Example: ['Sprint 1', 'Sprint 2']",
    )
    version_filter: Optional[list[str]] = Field(
        default=None,
        description="Filter tasks by fix version. Only tasks with these versions will be synced. Example: ['04.10.05', '04.11.06']",
    )


class ProjectBoardsConfig(BaseModel):
    """Configuration for all boards in a project."""

    developer_board: BoardConfig = Field(
        description="Developer board configuration (required) - technical tasks",
    )
    pm_board: Optional[BoardConfig] = Field(
        default=None,
        description="PM board configuration (optional) - PM overview/features/release notes",
    )


class ProjectConfig(BaseModel):
    """Configuration for a single project in SynthPM."""

    project_key: str = Field(
        description="Jira project key",
    )
    spreadsheet_id: str = Field(
        description="Google Sheets spreadsheet ID",
    )
    google_sheets_token_path: str = Field(
        default="pm-684f8662ca98.json",
        description="Path to Google Sheets API token",
    )
    boards: ProjectBoardsConfig = Field(
        description="Board configurations",
    )
    telegram: TelegramConfig = Field(
        description="Telegram configuration",
    )
    sync_settings: SyncSettings = Field(
        default_factory=SyncSettings,
        description="Sync settings",
    )
    gid: Optional[int] = Field(
        default=None,
        description="Google Docs GID (legacy)",
    )
    google_docs_id: Optional[str] = Field(
        default=None,
        description="Google Docs document ID",
    )
    google_docs_url: Optional[str] = Field(
        default=None,
        description="Google Docs URL",
    )


class SynthPMMultiProjectConfig(BaseModel):
    """Multi-project configuration for SynthPM."""

    projects: List[ProjectConfig] = Field(
        description="List of project configurations",
    )

    def get_project(self, project_key: str) -> Optional[ProjectConfig]:
        """Get project configuration by key.

        Args:
            project_key: Jira project key

        Returns:
            Project configuration if found, None otherwise
        """
        for project in self.projects:
            if project.project_key == project_key:
                return project
        return None

    def get_all_project_keys(self) -> List[str]:
        """Get all project keys.

        Returns:
            List of project keys
        """
        return [project.project_key for project in self.projects]


class ProjectStatusMapping(BaseModel):
    """Status mapping for a project."""

    google_sheet_to_jira: Dict[str, str] = Field(
        description="Mapping from Google Sheet status to Jira status",
    )
    jira_to_google_sheet: Dict[str, str] = Field(
        description="Mapping from Jira status to Google Sheet status",
    )


class ProjectInfo(BaseModel):
    """Project information from projects_info.json."""

    description: str
    key: str
    start_date: str
    keywords: List[str]


class ProjectMetadata(BaseModel):
    """Complete project metadata including status mappings."""

    project_info: ProjectInfo
    status_mapping: ProjectStatusMapping
    sprint_configuration: Dict
    departments: Dict
    components: List[Dict]
    assignees: List[Dict]
    epics: List[Dict]
    roadmap_notes: Optional[Dict] = None
