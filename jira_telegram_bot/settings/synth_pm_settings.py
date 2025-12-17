"""Settings for SynthPM feature."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional
from typing import TYPE_CHECKING

from pydantic import Field
from pydantic import field_validator
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from jira_telegram_bot.entities.synth_pm.project_config import (
    ProjectConfig,
    ProjectMetadata,
    SynthPMMultiProjectConfig,
)

if TYPE_CHECKING:
    from jira_telegram_bot.entities.synth_pm.sync_filter_criteria import (
        SynthPMSyncFilterCriteria,
    )


class SynthPMSettings(BaseSettings):
    """Settings for SynthPM feature integration with multi-project support."""

    # Configuration files
    story_sync_config_path: str = Field(
        default="config/story_sync_config.json",
        description="Path to story sync configuration file",
    )
    projects_info_path: str = Field(
        default="jira_telegram_bot/settings/projects_info.json",
        description="Path to projects info configuration file",
    )

    # Current project (can be overridden)
    current_project_key: Optional[str] = Field(
        default=None,
        description="Current active project key (defaults to first in config)",
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

    _multi_project_config: Optional[SynthPMMultiProjectConfig] = None
    _projects_metadata: Optional[Dict[str, ProjectMetadata]] = None

    def load_multi_project_config(self) -> SynthPMMultiProjectConfig:
        """Load multi-project configuration from JSON file.

        Returns:
            Multi-project configuration
        """
        if self._multi_project_config is not None:
            return self._multi_project_config

        config_path = Path(self.story_sync_config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, encoding="utf-8") as f:
            config_data = json.load(f)

        self._multi_project_config = SynthPMMultiProjectConfig(**config_data)
        return self._multi_project_config

    def load_projects_metadata(self) -> Dict[str, ProjectMetadata]:
        """Load projects metadata including status mappings.

        Returns:
            Dictionary of project metadata by project key
        """
        if self._projects_metadata is not None:
            return self._projects_metadata

        metadata_path = Path(self.projects_info_path)
        if not metadata_path.exists():
            raise FileNotFoundError(f"Projects info file not found: {metadata_path}")

        with open(metadata_path, encoding="utf-8") as f:
            metadata_raw = json.load(f)

        self._projects_metadata = {
            key: ProjectMetadata(**value) for key, value in metadata_raw.items()
        }
        return self._projects_metadata

    def get_project_config(self, project_key: Optional[str] = None) -> ProjectConfig:
        """Get project configuration by key.

        Args:
            project_key: Project key (uses current_project_key if None)

        Returns:
            Project configuration

        Raises:
            ValueError: If project not found
        """
        multi_config = self.load_multi_project_config()

        if project_key is None:
            project_key = self.current_project_key

        if project_key is None:
            if multi_config.projects:
                return multi_config.projects[0]
            raise ValueError("No projects configured")

        project = multi_config.get_project(project_key)
        if project is None:
            raise ValueError(f"Project not found: {project_key}")

        return project

    def get_project_metadata(self, project_key: str) -> ProjectMetadata:
        """Get project metadata including status mappings.

        Args:
            project_key: Project key

        Returns:
            Project metadata

        Raises:
            ValueError: If project metadata not found
        """
        metadata = self.load_projects_metadata()
        if project_key not in metadata:
            raise ValueError(f"Project metadata not found: {project_key}")
        return metadata[project_key]

    def get_all_projects(self) -> List[ProjectConfig]:
        """Get all project configurations.

        Returns:
            List of all project configurations
        """
        multi_config = self.load_multi_project_config()
        return multi_config.projects

    def get_telegram_bot_token(self, project_key: Optional[str] = None) -> str:
        """Get Telegram bot token for a project from environment.

        Args:
            project_key: Project key

        Returns:
            Telegram bot token
        """
        project = self.get_project_config(project_key)
        token = os.getenv(project.telegram.bot_token_env)
        if not token:
            raise ValueError(
                f"Telegram bot token not found in env: {project.telegram.bot_token_env}",
            )
        return token

    def get_telegram_channel_id(self, project_key: Optional[str] = None) -> str:
        """Get Telegram channel ID for a project from environment.

        Args:
            project_key: Project key

        Returns:
            Telegram channel ID
        """
        project = self.get_project_config(project_key)
        channel_id = os.getenv(project.telegram.channel_id_env)
        if not channel_id:
            raise ValueError(
                f"Telegram channel ID not found in env: {project.telegram.channel_id_env}",
            )
        return channel_id

    def get_telegram_group_id(self, project_key: Optional[str] = None) -> str:
        """Get Telegram group ID for a project from environment.

        Args:
            project_key: Project key

        Returns:
            Telegram group ID
        """
        project = self.get_project_config(project_key)
        group_id = os.getenv(project.telegram.group_id_env)
        if not group_id:
            raise ValueError(
                f"Telegram group ID not found in env: {project.telegram.group_id_env}",
            )
        return group_id

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

