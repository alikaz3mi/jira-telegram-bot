from __future__ import annotations

import json
import os
from typing import Dict, Any

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot.use_cases.interfaces.project_info_repository_interface import (
    ProjectInfoRepositoryInterface,
)


class ProjectInfoRepository(ProjectInfoRepositoryInterface):
    """Repository for retrieving project information from JSON file storage."""

    def __init__(self, file_path: str = None):
        """Initialize project info repository.

        Args:
            file_path: Path to the projects info JSON file.
                      If not provided, uses default path.
        """
        self.file_path = file_path or os.path.join(
            DEFAULT_PATH, "jira_telegram_bot/settings/projects_info.json"
        )

    async def get_project_info(self, project_key: str) -> Dict[str, Any]:
        """Retrieve project information by project key.

        Args:
            project_key: The project key to retrieve information for.

        Returns:
            Dictionary containing project information.

        Raises:
            ValueError: If no project information is found for the given project key.
            FileNotFoundError: If the projects info file doesn't exist.
        """
        with open(self.file_path, "r") as f:
            projects_info = json.load(f)
            
        project_info = projects_info.get(project_key)
        if not project_info:
            raise ValueError(f"No project info found for {project_key}")
            
        return project_info